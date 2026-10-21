0005: Poll publishes, push proposes, one ingest path
====================================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

Records arrive two ways: the published or default branch of a source,
and CI pipelines on feature branches.
A pushed proposal must never overwrite what is published,
and both paths must parse, validate and hash identically so approval
evidence carries over.

Decision
--------

Polling reads only each registration's ``published_ref`` and writes
**published** rows.
Push intake (``PUT``/``POST /api/v1/candidates``) writes only
**candidate** rows and refuses the literal published ref.
Both go through ``app.services.ingest``
(``prepare_document`` then ``ingest_document``).
Published rows are unique per ``(source_id, project, path)``;
candidates per ``(source_id, project, record_key, ref)``.

Consequences
------------

* A push can never create, replace or delete a published row.
* Identical bytes produce the same digest on both paths, which makes
  promotion work (:doc:`0006-content-digest-approval`).
* For ``published_ref: "@project-default"`` the real default branch is
  unknown without a source call, which intake never makes,
  so a push to that branch is stored as a candidate.
  Polling still owns the published row.
