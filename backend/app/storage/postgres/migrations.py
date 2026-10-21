"""
Apply the Alembic migrations under a PostgreSQL advisory lock.

Used by ``adriano migrate`` and ``adriano serve`` (migrate-on-start).
Several replicas or an init container may start at the same time: each
one first takes the session-level advisory lock
:data:`MIGRATION_LOCK_KEY` on a dedicated connection, holds it while
``alembic upgrade head`` runs on its own connection, and releases it
afterwards. A process that waits for the lock finds the schema already
at head and upgrades nothing.

Public API: :data:`MIGRATION_LOCK_KEY`, :func:`alembic_ini_path`,
:func:`upgrade_to_head`.
"""

import logging
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import NullPool

import app
from alembic import command
from app.database import _make_engine_url
from app.errors import ConfigurationError

logger = logging.getLogger(__name__)

#: Single-key (``bigint``) advisory lock serialising migrations: the
#: ASCII bytes of ``adriano!`` read as a big-endian integer. Single-key
#: and two-key advisory locks never conflict in PostgreSQL, so this is
#: independent of the registration locks
#: (:data:`app.storage.postgres.store.LOCK_NAMESPACE`).
MIGRATION_LOCK_KEY = 0x61647269616E6F21


def alembic_ini_path() -> Path:
    """
    Locate ``alembic.ini``.

    It sits next to the ``app`` package in the repository
    (``backend/``) and in the container image (``/app``); the working
    directory is tried as a fallback.

    :returns: The file.
    :raises ConfigurationError: If it is in neither place.
    """
    package_parent = Path(app.__file__).resolve().parent.parent
    for directory in (package_parent, Path.cwd()):
        candidate = directory / "alembic.ini"
        if candidate.is_file():
            return candidate
    raise ConfigurationError(
        f"alembic.ini not found in {package_parent} or {Path.cwd()}: run "
        "the command from the backend directory (or /app in the image)"
    )


def upgrade_to_head(database_url: str) -> None:
    """
    Run ``alembic upgrade head`` while holding the migration lock.

    Blocks until the lock is free. The lock is released when the
    upgrade ends, also on failure (and by PostgreSQL if the process
    dies, since it belongs to the lock connection's session).

    :param database_url: Plain ``postgresql://`` DSN.
    :raises sqlalchemy.exc.SQLAlchemyError: If the database is
        unreachable or a migration fails.
    :raises ConfigurationError: If ``alembic.ini`` cannot be found.
    """
    config = Config(str(alembic_ini_path()))
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    engine = create_engine(
        _make_engine_url(database_url),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    try:
        with engine.connect() as lock_connection:
            logger.info("waiting for the migration lock")
            lock_connection.execute(
                select(func.pg_advisory_lock(MIGRATION_LOCK_KEY))
            )
            try:
                logger.info("migration lock held: upgrading to head")
                command.upgrade(config, "head")
            finally:
                lock_connection.execute(
                    select(func.pg_advisory_unlock(MIGRATION_LOCK_KEY))
                )
    finally:
        engine.dispose()
