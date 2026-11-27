Database schema
===============

The schema is owned by the Alembic migrations in
``backend/alembic/versions``;
:mod:`app.storage.postgres.models` only mirrors it for querying and is
never used to create tables outside tests.
Triggers and column comments exist only in the migrations.

Migrations
----------

``0001_initial``
   All tables, the partial unique index ``uq_record_published_uuid``,
   the GIN index on the search vector, the partial expression index on
   ``links ->> 'corrects'`` and ``COMMENT ON`` for non-obvious
   objects.

``0002_triggers_and_search``
   The search-vector trigger and the append-only triggers on
   ``decision_event`` (``UPDATE``, ``DELETE`` and ``TRUNCATE``) with
   their functions.

Every migration is hand-written and has a working ``downgrade()``.

Tables
------

.. md-mermaid::

   erDiagram
     source_registration ||--o{ record : "source_id"
     source_registration ||--o{ not_indexed : "source_id"
     revision ||--o{ record : "digest, previous_digest"
     revision ||--o{ decision_event : "digest"
     revision ||--o{ not_indexed : "digest"
     record }o..o{ decision_event : "adr_uuid, no FK"

     source_registration {
       text id PK "id from catalog.yaml"
       text type "filesystem or gitlab"
       jsonb config "secrets excluded"
       bool enabled
       text last_status "never ok partial failed disabled"
     }
     revision {
       text digest PK "sha256-v1:hex"
       text content "canonical text"
     }
     record {
       uuid adr_uuid PK "the authored UUID"
       text kind PK "published or candidate"
       text ref PK
       text source_id FK
       text project
       text path
       text digest FK
       text previous_digest FK
       text record_kind "decision or erratum"
       jsonb links
       jsonb erratum "errata only"
       tsvector search
     }
     decision_event {
       uuid id PK
       uuid adr_uuid
       text digest FK
       text action "accepted or rejected"
       text actor_issuer
       text actor_subject
       text policy_id
       int policy_version
       timestamptz created_at
     }
     not_indexed {
       text source_id PK
       text project PK
       text path PK
       text ref PK
       text origin "poll or push"
       jsonb reasons
       text digest FK "nullable"
       uuid holder_uuid "duplicates only"
       timestamptz first_seen_at
       timestamptz last_seen_at
     }
     intake_run {
       uuid id PK
       text source_id "no FK"
       text kind "poll or push"
       text delivery_id
       text status "running ok partial failed"
     }

``source_registration``
   One row per registration in ``catalog.yaml``, synced at startup.
   Removed registrations are disabled with a ``config_error``, never
   deleted, so their records and not-indexed entries keep their
   foreign keys.
   Also holds poll status: ``last_attempt_at``, ``last_success_at``,
   ``last_status`` and ``last_error`` (JSON, no secrets).

``revision``
   Immutable, content-addressed snapshots: the canonical text of every
   content version ever indexed, keyed by digest.
   Diffs and approval evidence refer to it.
   Rows are inserted with ``ON CONFLICT DO NOTHING`` and are never
   updated.

``record``
   One row per published ADR or candidate (see :doc:`records`).
   The primary key is ``(adr_uuid, kind, ref)``; source, project and
   path are plain attributes.
   Beyond the columns in the diagram it stores ``change_token``,
   ``metadata`` (the parsed frontmatter), ``title`` and
   ``title_source``, ``decision_date`` and ``decision_date_inferred``,
   ``rendered_html`` (sanitized), ``issues`` (per-document issues),
   ``source_url``, ``author``, and the timestamps ``first_seen_at``,
   ``updated_at`` and ``last_seen_at``.

``decision_event``
   The append-only approval history (see :doc:`approval`).
   Beyond the diagram it stores ``actor_display``,
   ``actor_email``, ``comment`` and ``provenance``
   (kind, source, project, ref, path and source URL at decision time,
   a snapshot that is never read back as a reference).
   It refers to the ADR by ``adr_uuid``, not by foreign key,
   because the decision outlives any one row: a published row created
   later with the same UUID and digest inherits the decision.

``not_indexed``
   One row per document intake could not index, keyed by location and
   ref (see :doc:`records`).
   It stores the ``reasons`` (JSON issues), the digest of the rejected
   content in ``revision`` when it could be read, ``holder_uuid`` for a
   duplicate, ``change_token`` (so a poll can skip an unchanged file;
   empty makes the next poll read it again) and ``source_url``.
   Rows are removed only by intake.

``intake_run``
   One row per poll of a registration and per push request,
   with ``identity`` (who triggered it, no secrets), ``started_at``,
   ``finished_at``, ``counts`` and ``errors``.
   ``source_id`` has no foreign key so that refused pushes naming an
   unknown registration are still logged.

Constraints and indexes
-----------------------

``uq_record_published_uuid``
   Unique ``adr_uuid`` where ``kind = 'published'``:
   one published row per ADR.
   Together with the primary key ``(adr_uuid, kind, ref)`` it also
   makes candidates unique per UUID and ref.

``ix_record_location``
   ``(source_id, project, path)``, not unique.
   A listing knows paths before it knows content, so change-token
   lookups use it.

``ix_record_search``
   GIN index on ``record.search``.

``ix_record_links_corrects``
   Partial expression index on ``links ->> 'corrects'``, only for rows
   that have the link (errata).

``uq_decision_event_uuid_digest``
   Unique ``(adr_uuid, digest)``:
   one formal decision per content revision.
   It also serves every approval-state lookup.

``uq_intake_run_delivery``
   Unique ``(source_id, delivery_id)`` where ``delivery_id`` is set,
   for retry deduplication of pushes.

``CHECK`` constraints restrict the enumerated text columns
(``kind``, ``title_source``, ``record_kind``, ``action``,
``last_status``, ``origin`` of a not-indexed entry, intake ``kind`` and
``status``).

Triggers
--------

``record_search_vector``
   ``BEFORE INSERT OR UPDATE OF title, adr_uuid, project, path, digest``
   on ``record``.
   It reads the body from ``revision`` and builds the weighted vector:
   title (A); UUID, project and path, with the path also split at ``/``
   and ``.`` (B); the body with the ``simple`` configuration (C);
   the body with ``english`` stemming (D).
   A trigger is used instead of a generated column because the body
   lives in another table.

``decision_event_append_only``
   A statement-level ``BEFORE UPDATE OR DELETE`` trigger that raises
   ``restrict_violation``, so even an ``UPDATE`` matching no rows fails.

``decision_event_no_truncate``
   The same function for ``TRUNCATE``.

The triggers protect against application bugs and mistakes, not against
a table owner or superuser, who can drop them.
Running the application as a role that does not own the tables is the
stronger, still non-cryptographic, mitigation;
see :doc:`/developer/security`.
