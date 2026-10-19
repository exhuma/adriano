"""Application factory for the adriano backend.

The FastAPI application is always built through :func:`create_app`.
Routers, middleware, and exception handlers are registered inside the
factory; nothing is registered at import time outside of it.
"""

from fastapi import FastAPI

from app.errors import register_handlers
from app.routers import health


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    :returns: A fully configured :class:`~fastapi.FastAPI` instance
        with routers and exception handlers registered.
    """
    app = FastAPI(title="adriano", docs_url="/api/docs")

    app.include_router(health.router)

    register_handlers(app)

    return app


app = create_app()
