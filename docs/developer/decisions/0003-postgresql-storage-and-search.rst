0003: PostgreSQL for storage and full-text search
=================================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

Approval evidence must be durable (an in-memory store is not
acceptable), and search must cover titles, Markdown bodies and useful
metadata with a P95 under one second.
The specification also asked that catalog logic not depend on a
particular database product.

Decision
--------

Use PostgreSQL through psycopg 3, SQLAlchemy 2 and Alembic.
Search uses a weighted ``tsvector`` column on ``record``
(title A; UUID, project and path B; body C with the ``simple``
configuration; body D with ``english`` stemming),
maintained by a trigger and indexed with GIN.
Services depend only on the ``CatalogStore`` protocol in
:mod:`app.storage.port`; :mod:`app.storage.postgres` is its only
implementation.

Consequences
------------

* No second stateful service for search.
* The ``simple`` configuration keeps identifiers, UUIDs and paths
  searchable as exact tokens; ``english`` adds stemmed body matches.
* Concurrency relies on PostgreSQL features (advisory locks,
  ``ON CONFLICT``, partial unique indexes); a port implementation for
  another database would have to provide equivalents.
* Measured headroom is large; see :doc:`/developer/performance`.
