0004: Serve every read from the local index
===========================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

The legacy viewer scraped its source on every request to ``/adr/``,
which made reads slow and coupled the catalog's availability to the
source's.

Decision
--------

Normal browse, search, filter, detail, diff and sources requests read
only from PostgreSQL.
Source adapters are constructed only by the polling service.
The old ``/adr/`` route is gone; JSON lives under ``/api/v1`` and the
SPA renders it.
``/healthz`` keeps its path.

Consequences
------------

* A source outage never breaks browsing; the UI shows freshness and a
  stale or failed banner instead of claiming the index is current.
* Published content is only as fresh as the last successful poll.
* ``tests/routers/test_no_adapter_calls.py`` patches every adapter
  constructor to raise and exercises every read route.
