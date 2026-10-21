"""Application factory for the adriano backend.

The FastAPI application is always built through :func:`create_app`.
Routers, middleware, and exception handlers are registered inside the
factory; nothing is registered at import time outside of it.

The lifespan loads ``catalog.yaml`` and syncs source registrations
(:func:`app.composition.start_catalog`). Startup never fails because of
the configuration or the database: problems are logged and reported by
``/healthz``.

Authentication: every ``/api/v1`` route requires a bearer token
(:mod:`app.auth`) -- an OIDC/dev JWT, except candidate intake
(``/api/v1/candidates``), which accepts only per-registration CI push
tokens (:mod:`app.auth.push`); ``/healthz`` and the OpenAPI schema/docs
(``/openapi.json``, ``/api/docs``) are public -- they expose no record
data or secrets. The dev-only ``/auth/dev`` router is imported and
mounted only when ``ADRIANO_DEV_AUTH_ENABLED`` is true and
``ADRIANO_DEV_SHARED_SECRET`` is set (see ``module-dev-auth-bypass``).

When ``ADRIANO_STATIC_DIR`` is set, the same process also serves the
built SPA, its ``/config.js`` and the security headers
(:func:`app.web.mount_spa`), registered after every API router so the
API keeps precedence.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth.tokens import AuthStatus, auth_status
from app.composition import start_catalog
from app.config import Settings, get_settings
from app.errors import register_handlers
from app.routers import (
    candidates,
    decisions,
    facets,
    health,
    me,
    records,
    sources,
)
from app.web import mount_spa

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Load the catalog configuration and sync registrations at startup.

    Settings come from the ``get_settings`` dependency, honouring a
    dependency override (used by tests).

    :param app: The application.
    :returns: An async context manager spanning the app lifetime.
    """
    settings_factory = app.dependency_overrides.get(get_settings, get_settings)
    app.state.catalog = start_catalog(settings_factory())
    yield


def _mount_dev_auth(app: FastAPI, settings: Settings) -> None:
    """
    Mount the dev router (token, roles) only when it is enabled.

    :param app: The application under construction.
    :param settings: Application settings.
    """
    if not settings.dev_auth_enabled:
        return
    if not settings.dev_shared_secret:
        logger.error(
            "ADRIANO_DEV_AUTH_ENABLED is true but ADRIANO_DEV_SHARED_SECRET "
            "is not set: /auth/dev is NOT mounted"
        )
        return
    # Imported and mounted ONLY here, so /auth/dev/* is a plain 404
    # whenever dev auth is disabled.
    from app.routers import auth_dev

    app.include_router(auth_dev.router)
    logger.warning(
        "DEV AUTH ENABLED: /auth/dev/token and /auth/dev/roles are "
        "mounted; the token route mints tokens "
        "for any identity. Never enable ADRIANO_DEV_AUTH_ENABLED in "
        "production."
    )


def _log_auth_status(settings: Settings) -> None:
    """
    Log which token validators are active.

    :param settings: Application settings.
    """
    status = auth_status(settings)
    if status is AuthStatus.UNCONFIGURED:
        logger.error(
            "authentication is not configured: every /api/v1 route "
            "answers 503; set ADRIANO_OIDC_AUTHORITY"
        )
    elif status is not AuthStatus.OIDC:
        logger.warning(
            "ADRIANO_DEV_SHARED_SECRET is set: dev HS256 tokens are "
            "accepted. It must be unset in production."
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the configured FastAPI application.

    :param settings: Settings deciding which routers are mounted (dev
        auth, SPA) and the reported version; defaults to
        :func:`app.config.get_settings`. Request-time settings still
        come from the ``get_settings`` dependency.
    :returns: A fully configured :class:`~fastapi.FastAPI` instance
        with routers and exception handlers registered.
    :raises ConfigurationError: If ``static_dir`` is set but holds no
        ``index.html``.
    """
    settings = settings or get_settings()
    app = FastAPI(
        title="adriano",
        version=settings.version,
        docs_url="/api/docs",
        lifespan=_lifespan,
    )

    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(records.router)
    app.include_router(sources.router)
    app.include_router(facets.router)
    app.include_router(decisions.router)
    app.include_router(candidates.router)
    _mount_dev_auth(app, settings)
    _log_auth_status(settings)

    register_handlers(app)
    if settings.static_dir is not None:
        mount_spa(app, settings)

    return app


app = create_app()
