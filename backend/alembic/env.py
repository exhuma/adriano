"""Alembic environment, wired to the application Settings.

The database URL is never read from ``alembic.ini``; it comes from
the same :class:`app.config.Settings` object the application uses,
with the ``+psycopg`` dialect modifier injected the same way.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.storage.postgres.models  # noqa: F401  (registers the tables)
from alembic import context
from app.config import get_settings
from app.database import Base, _make_engine_url

target_metadata = Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
# Programmatic callers (the test suite) pass
# ``attributes["configure_logger"] = False`` so running migrations does
# not reconfigure (and disable) the caller's loggers.
if config.config_file_name is not None and config.attributes.get(
    "configure_logger", True
):
    fileConfig(config.config_file_name)

# Programmatic callers (the test suite) may pass a plain DSN through
# ``Config.attributes["database_url"]``; otherwise use the app Settings.
config.set_main_option(
    "sqlalchemy.url",
    _make_engine_url(
        config.attributes.get("database_url")
        or str(get_settings().database_url)
    ),
)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an
    Engine, though an Engine is acceptable here as well. By
    skipping the Engine creation we don't even need a DBAPI to be
    available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
