0007: Approval history lives in the database, append-only
=========================================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

Legacy ADRs carried a ``signed-off-by`` list in their frontmatter,
which anybody could edit and nothing verified.
The specification required authenticated, durable, auditable approval
separate from authored content.

Decision
--------

Store decisions as rows of ``decision_event`` with the authenticated
``issuer|subject``, action, server timestamp, policy id and version,
comment and provenance.
Database triggers refuse ``UPDATE``, ``DELETE`` and ``TRUNCATE`` on that
table.
Keep parsing ``signed-off-by`` and show it as
"Legacy sign-off (unverified)"; it never counts as approval.

Consequences
------------

* Authors only write Markdown; reviewers act in the catalog.
* History survives restarts and re-indexing; intake never touches it.
* The triggers stop bugs and mistakes, not a table owner or
  superuser. Tamper evidence is out of scope
  (:doc:`/developer/domain/hashing`, :doc:`/developer/security`).
