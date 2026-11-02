"""
Catalog persistence.

Services depend only on :mod:`app.storage.port` (the DB-neutral
:class:`~app.storage.port.CatalogStore` protocol and its value types)
and :mod:`app.storage.session_port` (sign-in sessions).
The PostgreSQL implementation lives in :mod:`app.storage.postgres` and is
wired in at the composition root.
"""
