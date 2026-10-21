0018: Compute relationship issues at read time
==============================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

``missing_target``, ``ambiguous_target`` and ``duplicate_uuid`` depend
on other records, including records of other registrations,
which can change without the record itself changing.

Decision
--------

Ingest stores only per-document issues.
Relationship issues are computed on the detail request from a
``RelationshipIndex`` built from the published rows that can affect
that one record, plus the record's own identity siblings.

Consequences
------------

* Issues are never stale after another registration changes.
* Candidates of *other* identities are not link targets and do not
  participate in duplicate detection.
* The targeted fetch keeps the detail request cheap;
  see :doc:`/developer/performance`.
