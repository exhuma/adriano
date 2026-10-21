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
   All tables, partial unique indexes, the search-vector trigger and
   GIN index, the append-only trigger on ``decision_event``
   (``UPDATE`` and ``DELETE``) and ``COMMENT ON`` for non-obvious
   columns.

``0002_no_truncate_decisions``
   A ``BEFORE TRUNCATE`` trigger on ``decision_event`` reusing the same
   function.

``0003_erratum_content``
   ``record.erratum`` and the ``ix_record_links_corrects`` index.
   It also clears the change token of erratum rows stored earlier,
   so the next poll re-ingests them with the current parser.

Every migration is hand-written and has a working ``downgrade()``.

Tables
------

.. mermaid::

   erDiagram
     source_registration ||--o{ record : "source_id"
     source_registration ||--o{ decision_event : "source_id"
     revision ||--o{ record : "digest, previous_digest"
     revision ||--o{ decision_event : "digest"
     record }o..o{ decision_event : "identity, no FK"

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
       uuid id PK "surrogate, used in URLs"
       text kind "published or candidate"
       text source_id FK
       text project
       text path
       text ref
       text record_key "UUID or src: fallback"
       uuid adr_uuid "nullable"
       text digest FK
       text previous_digest FK
       text record_kind "decision or erratum"
       jsonb links
       jsonb erratum "errata only"
       tsvector search
     }
     decision_event {
       uuid id PK
       text source_id FK
       text project
       text record_key
       text digest FK
       text action "accepted or rejected"
       text actor_issuer
       text actor_subject
       text policy_id
       int policy_version
       timestamptz created_at
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
   deleted, so their records and decisions keep their foreign keys.
   Also holds poll status: ``last_attempt_at``, ``last_success_at``,
   ``last_status`` and ``last_error`` (JSON, no secrets).

``revision``
   Immutable, content-addressed snapshots: the canonical text of every
   content version ever indexed, keyed by digest.
   Diffs and approval evidence refer to it.
   Rows are inserted with ``ON CONFLICT DO NOTHING`` and are never
   updated.

``record``
   One row per published file or candidate (see :doc:`records`).
   Beyond the columns in the diagram it stores ``change_token``,
   ``metadata`` (the parsed frontmatter), ``title`` and
   ``title_source``, ``decision_date`` and ``decision_date_inferred``,
   ``rendered_html`` (sanitized), ``issues`` (per-document issues),
   ``source_url``, ``author``, and the timestamps ``first_seen_at``,
   ``updated_at`` and ``last_seen_at``.

``decision_event``
   The append-only approval history (see :doc:`approval`).
   Beyond the diagram it stores ``adr_uuid`` (never null: records
   without a UUID cannot be decided), ``actor_display``,
   ``actor_email``, ``comment`` and ``provenance``
   (record id, kind, ref, path and source URL at decision time).
   It refers to records by logical identity, not by foreign key,
   because the decision outlives any one row: a published row created
   later with the same identity and digest inherits the decision.

``intake_run``
   One row per poll of a registration and per push request,
   with ``identity`` (who triggered it, no secrets), ``started_at``,
   ``finished_at``, ``counts`` and ``errors``.
   ``source_id`` has no foreign key so that refused pushes naming an
   unknown registration are still logged.

Constraints and indexes
-----------------------

``uq_record_published_location``
   Unique ``(source_id, project, path)`` where ``kind = 'published'``.

``uq_record_candidate_identity_ref``
   Unique ``(source_id, project, record_key, ref)`` where
   ``kind = 'candidate'``.

``ix_record_identity``
   ``(source_id, project, record_key)``, for siblings and decisions.

``ix_record_search``
   GIN index on ``record.search``.

``ix_record_links_corrects``
   Partial expression index on ``links ->> 'corrects'``, only for rows
   that have the link (errata).

``uq_decision_event_identity_digest``
   Unique ``(source_id, project, record_key, digest)``:
   one formal decision per content revision.
   It also serves every approval-state lookup.

``uq_intake_run_delivery``
   Unique ``(source_id, delivery_id)`` where ``delivery_id`` is set,
   for retry deduplication of pushes.

``CHECK`` constraints restrict the enumerated text columns
(``kind``, ``title_source``, ``record_kind``, ``action``,
``last_status``, intake ``kind`` and ``status``).

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
