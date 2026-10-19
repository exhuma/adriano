"""Application factory for the adriano backend.

The FastAPI application is always built through :func:`create_app`.
Routers, middleware, and exception handlers are registered inside the
factory; nothing is registered at import time outside of it.

The lifespan loads ``catalog.yaml`` and syncs source registrations
(:func:`app.composition.start_catalog`). Startup never fails because of
the configuration or the database: problems are logged and reported by
``/healthz``.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.composition import start_catalog
from app.config import get_settings
from app.errors import register_handlers
from app.routers import health


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


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    :returns: A fully configured :class:`~fastapi.FastAPI` instance
        with routers and exception handlers registered.
    """
    app = FastAPI(title="adriano", docs_url="/api/docs", lifespan=_lifespan)

    app.include_router(health.router)

    register_handlers(app)

    return app


app = create_app()
