"""
CSRF protection of cookie-authenticated requests.

The session cookie is ``SameSite=Strict`` already; on top of that
(RFC 10017 requires a CSRF defence besides ``SameSite``), every
cookie-authenticated request with an unsafe method, and the
``/auth/logout`` and ``/auth/dev/login`` posts, must carry:

- the header ``X-Adriano-CSRF: 1``. A cross-site form or a "simple"
  ``fetch`` cannot set a custom header, and a cross-origin script that
  tries triggers a CORS preflight this API never grants;
- an ``Origin`` header, *if present*, equal to the request's own
  origin.

Failures are HTTP 403 with code ``csrf_failed``. CI push requests
(bearer push token, no cookie) never pass through here.

The request's own origin is ``scheme://host[:port]`` from the ASGI
scope's scheme and the ``Host`` header, default ports dropped and
lower-cased. Behind a TLS-terminating proxy the scheme is only right
when Uvicorn trusts the proxy's ``X-Forwarded-Proto``
(``ADRIANO_FORWARDED_ALLOW_IPS``), and the proxy must pass the
browser's ``Host`` through unchanged: ``X-Forwarded-Host`` is not
honoured, so a client can never choose the origin it is compared with.

Public API: :data:`CSRF_HEADER`, :data:`UNSAFE_METHODS`,
:func:`request_origin`, :func:`check_csrf`, :func:`require_csrf`.
"""

from urllib.parse import urlsplit

from starlette.requests import Request

from app.errors import ForbiddenError

__all__ = [
    "CSRF_HEADER",
    "UNSAFE_METHODS",
    "check_csrf",
    "request_origin",
    "require_csrf",
]

CSRF_HEADER = "X-Adriano-CSRF"

#: Methods that need the CSRF header on cookie-authenticated requests.
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_DEFAULT_PORTS = {"http": 80, "https": 443}


def _normalise(scheme: str, netloc: str) -> str | None:
    """
    Build a comparable ``scheme://host[:port]``.

    :param scheme: URL scheme.
    :param netloc: Host and optional port.
    :returns: The origin, or ``None`` if it cannot be parsed.
    """
    try:
        parts = urlsplit(f"{scheme.lower()}://{netloc}")
        port = parts.port
    except ValueError:
        return None
    if not parts.hostname or parts.username or parts.password:
        return None
    origin = f"{parts.scheme}://{parts.hostname}"
    if port is not None and port != _DEFAULT_PORTS.get(parts.scheme):
        origin += f":{port}"
    return origin


def request_origin(request: Request) -> str:
    """
    Compute the origin the request was addressed to.

    :param request: The request.
    :returns: ``scheme://host[:port]`` (see the module docs).
    """
    url = request.url
    return _normalise(url.scheme, url.netloc) or f"{url.scheme}://{url.netloc}"


def _origin_matches(request: Request) -> bool:
    """
    Compare the ``Origin`` header with the request's own origin.

    :param request: The request.
    :returns: ``True`` when the header is absent or equal.
    """
    header = request.headers.get("origin")
    if header is None:
        return True
    try:
        parts = urlsplit(header)
    except ValueError:
        return False
    if parts.path or parts.query or parts.fragment:
        return False
    claimed = _normalise(parts.scheme, parts.netloc)
    return claimed is not None and claimed == request_origin(request)


def check_csrf(request: Request) -> None:
    """
    Enforce the CSRF header and the same-origin rule.

    :param request: The request.
    :raises ForbiddenError: Code ``csrf_failed`` (HTTP 403).
    """
    if request.headers.get(CSRF_HEADER) != "1":
        raise ForbiddenError(
            f"cross-site request refused: the {CSRF_HEADER}: 1 header is "
            "required",
            code="csrf_failed",
        )
    if not _origin_matches(request):
        raise ForbiddenError(
            "cross-site request refused: the Origin header does not match "
            "this site",
            code="csrf_failed",
        )


def require_csrf(request: Request) -> None:
    """
    FastAPI dependency: :func:`check_csrf` for the auth posts.

    :param request: The request.
    :raises ForbiddenError: Code ``csrf_failed`` (HTTP 403).
    """
    check_csrf(request)
