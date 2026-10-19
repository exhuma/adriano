"""
PostgreSQL implementation of :mod:`app.storage.port`.

Construct :class:`app.storage.postgres.store.PostgresStoreProvider` with
an engine at the composition root; nothing else should import from this
package outside tests and Alembic.
"""
