"""
Serve the built SPA and its runtime configuration from the API process.

Mounted by :func:`app.main.create_app` only when
``ADRIANO_STATIC_DIR`` is set (the single container image sets it to
the built ``dist/``). Routing, with the API keeping precedence:

- every API route (``/api/...``, ``/healthz``, ``/openapi.json``,
  ``/api/docs``, ``/auth/...``) is matched first and behaves as
  without the SPA;
- ``GET /config.js`` is rendered once from :class:`~app.config.Settings`
  (module-runtime-config-spa): ``window.__APP_CONFIG__ = {...};`` with
  exactly the keys of ``frontend/src/config.ts``'s ``RuntimeConfig``
  (``apiBaseUrl``, ``oidcEnabled``). It carries no OIDC client
  settings -- the backend signs users in -- and never a dev-auth flag;
- ``/assets/*`` (content-hashed bundle files) are served with a
  one-year ``immutable`` cache;
- any other ``GET``/``HEAD`` that matches no route serves an existing
  top-level file of the SPA directory (e.g. ``favicon.svg``) or else
  ``index.html`` with ``no-cache``, so history-mode deep links work.
  Unknown paths under the API prefixes (including ``/auth``) and
  missing assets stay plain JSON 404s.

The fallback is a ``404`` exception handler rather than a catch-all
route, so it never shadows a route and never turns an API ``405`` into
something else.

:class:`SecurityHeadersMiddleware` adds the headers nginx used to set
to every response (see :data:`CONTENT_SECURITY_POLICY`).

Public API: :func:`mount_spa`, :func:`render_config_js`,
:data:`CONTENT_SECURITY_POLICY`, :class:`SecurityHeadersMiddleware`.
"""

import json
import os
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException
from starlette.staticfiles import PathLike, StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings
from app.errors import ConfigurationError

#: Path prefixes that never fall back to ``index.html``: an unknown
#: path below them is a JSON 404. A prefix matches itself and anything
#: below ``<prefix>/``.
NO_FALLBACK_PREFIXES = (
    "/api",
    "/auth",
    "/healthz",
    "/openapi.json",
    "/assets",
    "/config.js",
)

#: Interactive API documentation pages (FastAPI's Swagger UI and
#: ReDoc), which load their scripts and styles from a CDN and use
#: inline scripts.
DOCS_PATHS = ("/api/docs", "/redoc")

NO_CACHE = "no-cache"
IMMUTABLE = "public, max-age=31536000, immutable"

#: CSP for the documentation pages: the SPA policy would block the CDN
#: assets and inline scripts of Swagger UI / ReDoc. Still no framing,
#: no foreign connections, no base or form targets.
DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net "
    "https://fonts.googleapis.com; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com "
    "https://cdn.redoc.ly; "
    "worker-src 'self' blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


#: The SPA's Content-Security-Policy. The browser talks only to this
#: origin (the backend runs the OIDC flow, so no IdP origin is
#: needed), and nothing is framed: ``frame-src 'none'``. Vuetify sets
#: theme CSS variables through inline ``style`` attributes, which needs
#: ``style-src 'unsafe-inline'`` (there is no nonce mechanism for style
#: attributes). ``script-src 'self'`` admits ``/auth/landing.js``.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; font-src 'self' data:; "
    "img-src 'self' data:; connect-src 'self'; "
    "frame-src 'none'; frame-ancestors 'none'; "
    "base-uri 'none'; form-action 'self'"
)


def render_config_js(settings: Settings) -> str:
    """
    Render ``/config.js`` from the settings.

    The object is JSON-encoded (no template substitution, so no
    injection), and every ``<`` is escaped so no value can close a
    ``<script>`` element even if the file is ever inlined.
    ``apiBaseUrl`` is always ``""``: the API is same-origin.
    ``oidcEnabled`` tells the SPA whether ``/auth/login`` is available.

    :param settings: Application settings.
    :returns: The JavaScript source.
    """
    config: dict[str, object] = {
        "apiBaseUrl": "",
        "oidcEnabled": settings.oidc_authority is not None,
    }
    encoded = json.dumps(config, indent=2).replace("<", "\\u003c")
    return f"window.__APP_CONFIG__ = {encoded};\n"


def _is_below(path: str, prefixes: tuple[str, ...]) -> bool:
    """
    Tell whether *path* is one of *prefixes* or below one of them.

    :param path: The request path.
    :param prefixes: Path prefixes without a trailing slash.
    :returns: Whether it matches.
    """
    return any(path == p or path.startswith(f"{p}/") for p in prefixes)


class SecurityHeadersMiddleware:
    """
    Add the security headers to every HTTP response.

    Applied to API responses as well: a CSP on JSON is harmless and
    protects against a response ever being rendered as a document.
    The documentation pages (:data:`DOCS_PATHS`) get :data:`DOCS_CSP`
    instead. A header the response already sets is left alone.

    :param app: The wrapped ASGI application.
    :param csp: The SPA's Content-Security-Policy.
    """

    def __init__(self, app: ASGIApp, csp: str) -> None:
        """
        Store the wrapped application and the policy.

        :param app: The wrapped ASGI application.
        :param csp: The SPA's Content-Security-Policy.
        """
        self.app = app
        self.csp = csp

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """
        Pass the request through, adding headers to the response.

        :param scope: ASGI scope.
        :param receive: ASGI receive channel.
        :param send: ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        docs = _is_below(scope["path"], DOCS_PATHS)
        defaults = (
            (b"x-content-type-options", b"nosniff"),
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            (
                b"content-security-policy",
                (DOCS_CSP if docs else self.csp).encode("latin-1"),
            ),
        )

        async def send_with_headers(message: Message) -> None:
            """
            Add the missing headers to the response start message.

            :param message: An outgoing ASGI message.
            """
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers.extend(
                    (name, value)
                    for name, value in defaults
                    if name not in present
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class _ImmutableStaticFiles(StaticFiles):
    """Static files with a one-year immutable cache (hashed assets)."""

    def file_response(
        self,
        full_path: PathLike,
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        """
        Build the file response and mark it immutable.

        :param full_path: The file to serve.
        :param stat_result: Its ``stat`` result.
        :param scope: ASGI scope.
        :param status_code: Response status.
        :returns: The response.
        """
        response = super().file_response(
            full_path, stat_result, scope, status_code
        )
        response.headers["Cache-Control"] = IMMUTABLE
        return response


def _check_static_dir(static_dir: Path) -> Path:
    """
    Ensure the SPA directory holds a build.

    :param static_dir: The configured directory.
    :returns: The resolved ``index.html``.
    :raises ConfigurationError: If ``index.html`` is missing.
    """
    index = static_dir / "index.html"
    if not index.is_file():
        raise ConfigurationError(
            f"ADRIANO_STATIC_DIR={static_dir} has no index.html: point "
            "it at the built SPA (frontend/dist), or unset it to serve "
            "the API only"
        )
    return index.resolve()


def _top_level_file(static_dir: Path, path: str) -> Path | None:
    """
    Find an existing top-level file of the SPA for *path*.

    Only a single path segment is considered, so no ``..`` or nested
    path can ever leave *static_dir*.

    :param static_dir: The SPA directory.
    :param path: The request path.
    :returns: The file, or ``None``.
    """
    name = path.removeprefix("/")
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    candidate = static_dir / name
    return candidate if candidate.is_file() else None


def mount_spa(app: FastAPI, settings: Settings) -> None:
    """
    Serve the SPA, ``/config.js`` and the security headers.

    Call after every API router is registered.

    :param app: The application under construction.
    :param settings: Application settings; ``static_dir`` must be set.
    :raises ConfigurationError: If ``static_dir`` is unset or holds no
        ``index.html``.
    """
    if settings.static_dir is None:
        raise ConfigurationError("mount_spa needs ADRIANO_STATIC_DIR")
    static_dir = settings.static_dir
    index = _check_static_dir(static_dir)
    config_js = render_config_js(settings)

    @app.get("/config.js", include_in_schema=False)
    def config_script() -> Response:
        """
        Serve the runtime configuration of the SPA.

        :returns: The rendered script, never cached.
        """
        return Response(
            config_js,
            media_type="application/javascript; charset=utf-8",
            headers={"Cache-Control": NO_CACHE},
        )

    app.mount(
        "/assets",
        _ImmutableStaticFiles(directory=static_dir / "assets", check_dir=False),
        name="assets",
    )

    async def spa_fallback(request: Request, exc: Exception) -> Response:
        """
        Answer an unmatched ``GET``/``HEAD`` with the SPA.

        :param request: The request no route matched.
        :param exc: The 404 raised by the router.
        :returns: A top-level file, ``index.html``, or the JSON 404.
        """
        if not isinstance(exc, HTTPException):
            # Status-code handlers only ever receive HTTPException.
            raise exc
        path = request.url.path
        if request.method not in ("GET", "HEAD") or _is_below(
            path, NO_FALLBACK_PREFIXES
        ):
            return await http_exception_handler(request, exc)
        found = _top_level_file(static_dir, path)
        if found is not None:
            return FileResponse(found)
        return FileResponse(index, headers={"Cache-Control": NO_CACHE})

    app.add_exception_handler(404, spa_fallback)
    app.add_middleware(SecurityHeadersMiddleware, csp=CONTENT_SECURITY_POLICY)
