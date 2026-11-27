Records
=======

A *record* is one indexed ADR or erratum, stored as a row of the
``record`` table.
This page covers how a file becomes a row, how rows are identified,
and how they relate to each other.
A file that cannot become a row is listed as not indexed instead;
see `Documents that are not indexed`_.

From file to row
----------------

Discovery
   Source adapters list files under the registration's ``path``
   (default ``doc/decisions``), recursively, and keep only file names
   matching ``^\d{4}-\d{2}-\d{2}-(.*)\.md$``
   (:py:obj:`app.domain.titles.is_adr_filename`).
   Other files, such as a ``README.md`` next to the ADRs, are ignored.

Parsing
   :py:obj:`app.domain.records.parse_record` turns the exact bytes into a
   ``ParsedRecord``.
   It never raises for content problems:
   every problem becomes an issue on the document,
   so one broken file never affects another.
   It splits the ``---`` frontmatter, loads it with
   ``yaml.safe_load``, validates known fields
   (:mod:`app.domain.validation`) and derives the title and date.

Title
   The ``title`` field, else the first ATX ``#`` heading outside code
   fences, else the humanised filename slug.
   ``title_source`` (``frontmatter``, ``h1`` or ``filename``) records
   which one was used.

Date
   ``decision-date`` only.
   A date taken from the filename prefix is stored with
   ``decision_date_inferred = true`` and always shown as inferred.

Kind
   ``record_kind`` is ``erratum`` when the frontmatter has
   ``erratum-for``, otherwise ``decision``.
   It is derived, never authored; see :doc:`errata`.

Rendering
   The Markdown body is rendered with markdown-it-py (CommonMark plus
   tables and strikethrough) and sanitized with nh3 at ingest.
   The stored ``rendered_html`` is safe to embed as-is.

Identity
--------

The ``uuid`` authored in the frontmatter is the only identity of an
ADR (:doc:`/developer/decisions/0023-uuid-is-the-only-identity`).
It is unique across all registrations and projects, written in lower
case, and never invented.
Source, project, path and ref are attributes of a row:
they say where the content was read from, not which ADR it is.

The primary key of ``record`` is ``(adr_uuid, kind, ref)``.
URLs and the API address an ADR as ``/records/{uuid}`` and a
candidate as ``/records/{uuid}/candidates/{ref}``.
Approval evidence is keyed by the UUID and a content digest
(:doc:`approval`).

Because the location is an attribute, a file that moves or is renamed
keeps its row, its URL, its history and its approvals.
A poll that finds a held UUID at a new location moves the row;
see `The holder rule`_.

Published and candidate rows
----------------------------

The ``kind`` column separates two states:

published
   Written only by polling, from the registration's ``published_ref``.
   There is at most one published row per UUID
   (``uq_record_published_uuid``).
   A complete poll deletes the published row of a file that is gone.

candidate
   Written only by CI push intake, from any other ref.
   Unique per ``(adr_uuid, ref)``,
   so several candidates of one ADR can exist on different refs
   ("competing candidates").
   Polling never deletes candidates.

All rows of one UUID are *siblings*:
revisions of one decision, never duplicates of each other.
The detail page lists them as other revisions.

The holder rule
~~~~~~~~~~~~~~~

The file already indexed under a UUID, the *holder*, keeps it.
:mod:`app.services.poll_apply` applies the rule to every fetched
document that carries a UUID *U* at a location *L*:

* nobody holds *U*: the document becomes the published row of *U*;
* the row of *U* is at *L*: the row is updated;
* the row of *U* is elsewhere, but its file released *U*: the row
  **moves** to *L*, keeping ``first_seen_at``, ``previous_digest`` and
  its approvals;
* otherwise the holder keeps *U* and the document at *L* is listed as
  not indexed with the reason ``duplicate_uuid``.

A holder's file releases its UUID only when it is known not to carry
it any more: its location is gone from a complete listing
(also when its project left a complete project listing or its
registration was removed from the configuration),
or it was read in this poll and carries another UUID or none.
A holder whose registration was not polled, or whose file could not
be read, keeps the UUID.

When several new files claim one UUID in the same poll, they are
applied in configuration order of their registration, then by project,
then by path, so the first one wins.
Registrations polled in one run are considered together,
so a file that moves from one registration to another in that run is a
move, not a delete and an insert.

A push follows a narrower rule: it is accepted for a UUID that
nobody holds or whose published holder is in the same registration and
project, and refused with ``409 duplicate_uuid`` otherwise
(see :doc:`/operator/ci-push`).

Documents that are not indexed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A document that cannot be indexed is not a record
(:doc:`/developer/decisions/0024-not-indexed-list`).
Intake writes it to the ``not_indexed`` table, keyed by
``(source_id, project, path, ref)``, with its origin (``poll`` or
``push``), its reasons (error issues), the digest of the rejected
content when it could be stored, the ``holder_uuid`` for a duplicate,
the source URL and the first and last time it was seen.

The reasons are issue codes:

``missing_frontmatter``, ``bad_yaml``, ``missing_uuid``, ``bad_uuid``
   The document has no valid UUID, so it has no identity.
   The codes explain why.

``duplicate_uuid``
   Another file holds the UUID.

``fetch_failed``
   The file could not be read at its source.

``bad_encoding``, ``uuid_mismatch``, ``published_ref_not_allowed``, ``content_too_large``
   A rejected push.
   ``bad_encoding`` also marks a polled file that is not valid UTF-8;
   if its UUID can still be read the file stays a record, but a
   blocked one.

Entries are cleared only by intake:

* when a poll indexes a document at that location;
* when a complete listing no longer contains the location;
* when its registration is removed from the configuration, whatever
  the origin of the entry;
* for a push entry, when a successful push or a poll indexes a
  document at the same file location, whatever the ref.

A poll never clears a push entry for not listing it,
because a pushed branch is not in the listing.
There is no manual dismiss.
``GET /api/v1/not-indexed`` and ``GET /api/v1/not-indexed/entry``
read the list; both need only ``read``.

Revisions and change tracking
-----------------------------

Every content version is stored once in the ``revision`` table,
keyed by its digest (see :doc:`hashing`).
A revision holds the canonical text (BOM removed, LF line endings),
not the raw bytes.
It is immutable and is what diffs and approval evidence refer to,
so a diff never needs the source's Git history.

On each row:

``digest``
   The current content revision.

``previous_digest``
   The digest the row had before its last content change.
   It is the fallback base of a diff when the ADR has no
   decisions.

``updated_at``
   Moves only when the digest changes, so "recently changed" sorting
   reflects content changes.

``last_seen_at``
   Moves on every upsert: the poll or push heartbeat.

``first_seen_at``
   Set once when the row is created.

``change_token``
   An opaque adapter value (for example ``mtime_ns:size`` or a GitLab
   blob id) that lets the next poll skip unchanged files without
   fetching them.

Relationships
-------------

Links are authored by UUID and stored as ``record.links`` JSON
(``app.domain.values.Links``):

``updates``
   From the newer decision to the earlier decision it updates.

``obsoletes``
   From the replacing decision to the decision it replaces.
   The legacy ``deprecates`` field is merged into it
   (``legacy_alias`` warning).

``corrects``
   From an erratum to the decision it corrects,
   authored as ``erratum-for``.

``app.domain.relationships.RelationshipIndex`` resolves a link to UUID
*U* when an ADR with that UUID is indexed.
An ADR is represented by its published row, else by its newest
candidate.
A UUID identifies exactly one ADR, so a link either resolves or does
not; there is nothing to choose between.

From resolved links the index derives the inbound links
(*updated by*, *obsoleted by*), the errata of a decision,
and a display status:
``obsoleted`` if anything obsoletes the record,
else ``updated`` if anything updates it,
else ``active``.
There is no authored status field
(:doc:`/developer/decisions/0014-derived-display-status`).

Relationships are resolved on the detail request only, from the
published rows that can affect that record plus its own siblings
(:doc:`/developer/decisions/0018-read-time-relationship-issues`).
Candidates of *other* ADRs are never link targets.

Validation issues
-----------------

Each problem is an ``app.domain.issues.Issue`` with a severity
(``error`` or ``warning``), a stable code and a short message meant for
readers.
Per-document issues are found by ``parse_record`` and stored in
``record.issues``; a document without a valid UUID keeps them as the
reasons of its not-indexed entry.
Relationship issues depend on other records and are computed when the
record is read; they are never stored.

Stored at ingest
~~~~~~~~~~~~~~~~

``bad_encoding`` : error
   The bytes are not valid UTF-8.
   The digest falls back to ``sha256-raw-v1`` and the record cannot be
   decided.

``bad_yaml`` : error
   The frontmatter is not valid YAML.
   No field is read, so the document also has no UUID and is not
   indexed.

``missing_frontmatter`` : error
   No ``---`` frontmatter block; the document is not indexed.

``missing_uuid``, ``bad_uuid`` : error
   No ``uuid``, or not a valid UUID; the document is not indexed.

``bad_date`` : error
   ``decision-date`` is not an ISO date.

``bad_field_type`` : error
   A known field has the wrong shape,
   for example ``updates`` that is not a list of UUIDs.

``missing_date`` : warning
   No ``decision-date``.

``unknown_field`` : warning
   A frontmatter key the catalog does not understand.

``legacy_alias`` : warning
   ``deprecates`` used; merged into ``obsoletes``.

``legacy_signoff`` : warning
   ``signed-off-by`` present; shown as unverified, never an approval.

``obsolete_kind_field`` : warning
   ``kind: decision`` present; ignored.

``legacy_erratum_format`` : error
   ``kind: erratum`` or a ``corrects`` key: the retired erratum shape.

Erratum-only codes are listed in :doc:`errata`.
``corrects_on_non_erratum`` is retired; it is no longer emitted but
still decodes from rows stored by earlier versions.

Computed when read
~~~~~~~~~~~~~~~~~~

``missing_target`` : warning
   A link's UUID matches no record.

``erratum_target_is_erratum`` : warning
   An erratum's ``erratum-for`` resolves to another erratum.

When a record can be decided
----------------------------

A stored row can be decided unless its file is not valid UTF-8
(:py:obj:`app.services.decisions.approval_blocker`;
:py:obj:`app.services.approval_view.is_approvable` is the same rule as
a flag).
A document without a valid UUID never becomes a record.
Other issues, including errors such as ``bad_date``, are shown but do
not block a decision.
