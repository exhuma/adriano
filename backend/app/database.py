"""Database engine, session factory, and the ORM declarative base.

Alembic owns all schema changes; this module never calls
``Base.metadata.create_all()`` outside of tests. The SQLAlchemy
``+psycopg`` dialect modifier is injected here at engine-construction
time so the configured DSN stays a portable, provider-neutral
``postgresql://`` URL.
"""

from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


def _make_engine_url(raw_url: str) -> str:
    """Inject the psycopg dialect modifier into a plain DSN.

    :param raw_url: Plain ``postgresql://`` DSN from configuration.
    :returns: The same URL with the ``+psycopg`` dialect modifier,
        ready for :func:`sqlalchemy.create_engine`.
    """
    return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)


@lru_cache
def get_engine(database_url: str) -> Engine:
    """Return a cached SQLAlchemy engine for the given DSN.

    Caching keyed by the plain DSN string lets dependency overrides
    (for example in tests) swap in a different database without
    reconstructing an engine on every call for the common case.

    :param database_url: Plain ``postgresql://`` DSN.
    :returns: A SQLAlchemy :class:`~sqlalchemy.Engine` for that DSN.
    """
    return create_engine(_make_engine_url(database_url))


def get_db(
    settings: Settings = Depends(get_settings),
) -> Generator[Session]:
    """Yield one request-scoped database session.

    The session is closed in a ``finally`` block regardless of
    whether the request raised an exception.

    :param settings: Application settings, injected so tests can
        override :func:`app.config.get_settings` with a different
        DSN.
    :returns: A generator yielding a single
        :class:`~sqlalchemy.orm.Session`.
    """
    engine = get_engine(str(settings.database_url))
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
