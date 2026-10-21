Invariants
==========

These rules must hold at all times.
A change that breaks one is a design change, not a bug fix,
and needs a new entry in :doc:`decisions/index`.
Each rule names where it is enforced and which tests pin it;
test paths are relative to ``backend/tests`` unless they start with
``frontend/``.

Sources and intake
------------------

Reads never call a source
   Browse, search, detail, diff, facets, sources and ``/me`` read only
   PostgreSQL.
   Source adapters are opened only through
   ``SourceBinding.open_adapter``, which only :mod:`app.services.polling`
   calls.

   *Tests:* ``routers/test_no_adapter_calls.py``
   (``test_every_read_route_never_constructs_an_adapter`` patches every
   adapter constructor to raise),
   ``routers/approval/test_candidates.py``
   (``test_intake_decisions_and_diff_never_open_an_adapter``).

Push never writes a published row
   :mod:`app.services.intake` always ingests as ``RecordState.CANDIDATE``
   and refuses the literal ``published_ref``.
   Published and candidate rows live under separate partial unique
   indexes, so an upsert of one kind cannot hit a row of the other.

   *Tests:* ``test_candidate_never_overwrites_published``,
   ``test_published_ref_is_refused``
   (``routers/approval/test_candidates.py``),
   ``test_partial_unique_indexes``
   (``storage/test_records.py``).

Polling writes only published rows and never deletes candidates
   Polling ingests as ``RecordState.PUBLISHED``.
   Its deletions go through ``CatalogStore.delete_published``,
   whose SQL is restricted to ``kind = 'published'``.

   *Tests:* none dedicated; see `Not enforced by a test`_.

An incomplete listing deletes nothing
   Nothing is deleted unless the project listing was complete,
   and within a project nothing unless its document listing was
   complete.
   A failed poll (no listing, adapter not opened, write failed) keeps
   all prior content.

   *Tests:* ``test_incomplete_listings_delete_nothing``,
   ``test_complete_poll_deletes_removed_files_and_projects``
   (``services/test_polling.py``),
   ``test_missing_root_fails_the_poll_and_keeps_records``
   (``services/test_filesystem_polling.py``),
   ``test_persistent_failure_is_partial_and_deletes_nothing``,
   ``test_failed_group_listing_deletes_nothing``
   (``services/test_gitlab_polling.py``).

Unchanged content is not fetched again
   Adapters compare change tokens; only documents marked changed are
   fetched.

   *Tests:* ``test_unchanged_tokens_are_not_fetched``
   (``services/test_polling.py``),
   ``test_second_poll_does_not_read_unchanged_files``,
   ``test_polls_ingest_then_skip_unchanged_branches``.

Poll and push share one ingest path
   Both call :py:obj:`app.services.ingest.prepare_document` and
   ``ingest_document``; nothing else writes record rows.

   *Tests:* ``services/test_ingest.py``.

Writes for one registration serialize
   Every write runs inside ``lock_registration``
   (a transaction-scoped advisory lock).

   *Tests:* ``storage/test_lock.py``.

Content and identity
--------------------

The digest depends only on canonical content
   :py:obj:`app.domain.hashing.content_digest` takes bytes only;
   no path, ref or registration enters it.
   The server always computes it: a client-supplied ``digest`` field is
   refused as unexpected.

   *Tests:* ``domain/test_hashing.py``,
   ``test_client_digest_is_refused``
   (``routers/approval/test_candidates.py``).

One broken file affects only itself
   :py:obj:`app.domain.records.parse_record` never raises for content
   problems; every problem becomes an issue on that record.

   *Tests:* ``domain/test_records.py``
   (``test_parse_record_never_raises``, property-based).

No UUID is ever invented
   :py:obj:`app.domain.values.record_key` falls back to
   ``src:<source_id>/<project>/<path>``.

   *Tests:* ``domain/test_records.py``.

Approval and audit
------------------

At most one decision per identity and digest
   ``uq_decision_event_identity_digest``;
   the insert uses ``ON CONFLICT DO NOTHING`` and a lost race becomes
   ``DecisionExistsError`` and HTTP 409 ``already_decided``.

   *Tests:* ``test_second_decision_for_digest_is_refused``
   (``storage/test_events.py``),
   ``test_deciding_twice_is_409``
   (``routers/approval/test_decisions.py``).

Decision history is append-only
   Statement-level triggers refuse ``UPDATE``, ``DELETE`` and
   ``TRUNCATE`` on ``decision_event``.
   No code path updates or deletes an event, and ingest never touches
   the table.

   *Tests:* ``test_decision_events_are_append_only``
   (``storage/test_events.py``),
   ``test_history_survives_a_new_app_and_is_append_only``
   (``routers/approval/test_decisions.py``).

SQL and Python agree on approval state
   ``approval_join`` mirrors :py:obj:`app.domain.approval.evaluate`.

   *Tests:* ``storage/test_approval_parity.py`` (every row, every
   policy variant, paged and unpaged).

A missing policy never means "not required"
   The loader yields ``policy_missing``; every decision is refused.

   *Tests:* ``test_missing_policy_refuses_decisions``
   (``routers/approval/test_decisions.py``),
   ``test_catalog_config.py``.

Unapprovable content cannot be decided
   No valid UUID or invalid UTF-8 means 409 ``not_approvable``.

   *Tests:* ``test_unapprovable_records_cannot_be_decided``
   (``routers/approval/test_decisions.py``).

Acceptance follows the digest, never the row
   Identical content on the published ref is accepted with its history;
   edited content is ``changed_since_acceptance``.

   *Tests:* ``routers/approval/test_lifecycle.py``
   (``test_identical_content_is_accepted_when_published``,
   ``test_edited_content_needs_new_approval_and_diffs``).

An erratum never changes its target
   Errata are decided on their own identity and digest.

   *Tests:* ``test_published_erratum_is_reported_then_verified_then_rejected``
   (``routers/approval/test_errata.py``).

Legacy sign-off is never approval
   ``signed-off-by`` is not an input to ``evaluate``.

   *Tests:* ``test_signoff_never_implies_approval``
   (``domain/test_records.py``).

Access
------

Every API route needs a token, except health and docs
   ``/api/v1`` routes depend on ``require_permission`` or the push-token
   check; ``/healthz``, ``/openapi.json`` and ``/api/docs`` are public
   and expose no record data.

   *Tests:* ``routers/test_auth.py``
   (``test_every_api_route_requires_authentication`` sweeps the OpenAPI
   schema, ``test_healthz_and_docs_stay_public``).

Read never implies review
   Eligibility comes from the policy only.

   *Tests:* ``test_reader_is_not_eligible``
   (``routers/approval/test_decisions.py``).

Push tokens only write candidates
   They are refused by read routes, and JWTs are refused by intake.

   *Tests:* ``test_push_token_cannot_read``,
   ``test_dev_jwt_is_refused_for_intake``
   (``routers/approval/test_candidates.py``).

The dev bypass needs both gates, and never reaches production builds
   See :doc:`security`.

   *Tests:* ``routers/test_auth.py``
   (``test_hs256_is_rejected_without_the_dev_secret``,
   ``test_rs256_token_is_accepted_and_never_routed_to_dev``,
   ``test_dev_router_is_absent_when_disabled``,
   ``test_dev_router_needs_the_secret``),
   ``routers/test_dev_roles.py``,
   ``frontend/scripts/check-no-dev-auth.sh`` (run by the frontend
   ``build`` script).

Rendered Markdown is sanitized before storage
   :py:obj:`app.services.ingest.render_markdown` passes every body through
   nh3; the frontend renders only that field with ``v-html``.

   *Tests:* ``services/test_ingest.py``
   (``test_render_markdown_sanitizes_html``,
   ``test_prepare_document_renders_sanitized_erratum_sections``).

Secrets are never logged or stored
   Tokens are referenced by env var name and held as secret strings.

   *Tests:* ``test_secrets_never_reach_storage_messages_or_logs``
   (``test_catalog_config.py``),
   ``test_token_never_appears_in_logs_or_problems``
   (``services/test_gitlab_polling.py``),
   ``test_intake_runs_are_recorded_without_the_token``
   (``routers/approval/test_candidates.py``).

Not enforced by a test
----------------------

The domain package is pure
   :mod:`app.domain` must not import FastAPI, SQLAlchemy, httpx or do
   file or network I/O (its only third-party import is PyYAML).
   No lint rule or test checks this today; it is kept by review.

Polling never deletes candidates
   Guaranteed by the ``kind`` filter in
   :py:obj:`app.storage.postgres.records.delete_published`,
   but no test polls a registration that also holds candidates and
   checks they survive a reconciling poll.
