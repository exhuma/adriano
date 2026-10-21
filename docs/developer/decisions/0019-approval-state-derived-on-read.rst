0019: Derive approval state on read, in SQL and in Python
=========================================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

The "needs approval" filter must paginate correctly,
so the approval state has to be known inside the search query.
Storing it would create a second copy that every decision and every
content change must keep in step.

Decision
--------

Derive the state from ``decision_event`` on every read.
``app.domain.approval.evaluate`` is the reference rule;
``app.storage.postgres.search.approval_join`` mirrors it in SQL with
set-based joins.
A parity test compares both for every row under every policy variant.

Consequences
------------

* No materialised state to repair; the append-only events are the only
  truth.
* The two implementations must change together;
  ``tests/storage/test_approval_parity.py`` fails otherwise.
* No extra index was needed at 20,000 records;
  see :doc:`/developer/performance`.
