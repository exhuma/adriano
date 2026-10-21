0006: Bind approval to identity and content digest
==================================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

An approval must apply to exactly the content that was reviewed,
regardless of branch, commit or file path,
and must survive the move from a feature branch to the default branch
when nothing changed.

Decision
--------

Every record gets a canonical ``sha256-v1`` digest of its complete file
(see :doc:`/developer/domain/hashing`).
Decisions are keyed by the logical identity
``(source_id, project, record_key)`` plus that digest,
with at most one decision per pair.
Approval state is a pure function of the identity's decisions and the
row's current digest (:doc:`/developer/domain/approval`).

Consequences
------------

* Promotion is implicit: a published row with the same identity and
  digest as an accepted candidate is accepted, with the full history.
  Nothing is copied.
* Any edit produces a new digest, so earlier acceptance does not count
  (``changed_since_acceptance``) and a diff is shown.
* A rejection is final for its digest; changed content gets a fresh
  decision.
* Promotion never crosses projects or registrations: the same UUID
  elsewhere is a different identity.
