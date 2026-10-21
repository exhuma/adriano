0002: One backend, one SPA, one database
========================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

The specification asked to keep parsing, sources, intake, lifecycle,
persistence, web and auth as separate concerns,
and to avoid a queue, search cluster, event bus or microservices
without a demonstrated need.

Decision
--------

Build a FastAPI backend (Python, uv) and a Vue 3 + Vuetify + TypeScript
frontend, following the ``stack-fastapi-vuetify`` route.
Separate concerns by package boundaries inside the one backend
(routers, services, domain, sources, storage, auth),
with :mod:`app.composition` as the only composition root.
Run PostgreSQL as the only stateful service.

Consequences
------------

* One image per tier and one database to back up.
* Concern boundaries are enforced by import discipline and tests,
  not by the network; see :doc:`/developer/architecture`.
* Scaling is horizontal: stateless backend replicas against one
  database.
* The database is a single failure domain for the whole catalog.
