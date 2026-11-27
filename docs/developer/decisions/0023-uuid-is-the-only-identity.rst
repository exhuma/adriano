0023: The ADR UUID is the only identity
=======================================

:Status: Accepted (supersedes :doc:`0013-fallback-identity`)
:Date: 2026-11-27

Context
-------

An ADR was identified by where its file lived:
a published row was unique per ``(source_id, project, path)``,
a candidate per ``(source_id, project, record_key, ref)``,
and approvals and URLs used that key or a surrogate row id.
A file without a UUID got the fallback key ``src:<source>/<project>/<path>``.

Moving or renaming a file therefore created a new ADR and lost its URL,
history and approvals.
Two files could carry one UUID and be shown as two ADRs,
and several rules existed only to manage that:
ownership of a location by configuration order,
resolution of a link to the nearest project, then registration,
then catalog, and a warning for ambiguous or duplicated UUIDs.

No deployment exists yet, so the model can change without a migration.

Decision
--------

The ``uuid`` authored in the frontmatter is the only identity of an ADR,
unique across all registrations and projects.
Source, project, path and ref are attributes of a row, never part of
its identity.

* A published row is the one row of its UUID.
  A candidate is a row of its UUID and ref.
  A decision belongs to a UUID and a content digest.
* A moved file keeps its row, URL, history and approvals:
  a poll that finds a UUID at a new location, because the holder's
  file left a complete listing or now carries another UUID,
  moves the row.
  This also holds across registrations polled in one run.
* The file already indexed under a UUID, the *holder*, keeps it.
  A second file claiming the same UUID is not indexed
  (:doc:`0024-not-indexed-list`).
  When several new files claim one UUID in one poll,
  configuration order decides, then project, then path.
* A push is accepted for a UUID nobody holds,
  or one held in the same registration and project;
  otherwise it is refused with ``409 duplicate_uuid``.
* A link names its target by UUID and resolves when that UUID is
  indexed.
  There are no resolution tiers and no ambiguity.
* URLs are ``/records/{uuid}`` and
  ``/records/{uuid}/candidates/{ref}``.
  The database has no surrogate record id.

Consequences
------------

* Reorganising folders, renaming files or moving a project to another
  registration changes nothing a reader or reviewer sees.
* A UUID copied into a second file by mistake never replaces the
  original; the copy is listed as not indexed until the author gives it
  a new UUID.
* A UUID can be unavailable to an author who does not know it is in
  use elsewhere.
  A pushed candidate for a UUID held in another project is refused, and
  the answer does not say where it is held.
* The ``ownership_conflict`` and cross-project ``duplicate_uuid``
  warnings and the ``ambiguous_target`` issue no longer exist.
* The initial migrations were rewritten in place;
  there is no upgrade path from an earlier schema.
