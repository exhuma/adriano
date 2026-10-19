# Status

Statuses: `todo`, `in-progress`, `done`, `blocked`.

| # | Phase | Status | Commit | Notes |
|---|---|---|---|---|
| 00 | Planning + phases folder | done | | spec copied, decisions recorded |
| 01 | Scaffold + skeleton UI | done | fcef2ad + next | see notes |
| 02 | Domain core | done | see git log | see notes |
| 03 | Persistence | done | see git log | see notes |
| 04 | Sources & ingest | todo | | |
| 05 | Browse slice | todo | | |
| 06 | Auth & RBAC slice | todo | | |
| 07 | Approval slice | todo | | |
| 08 | Samples, deploy, demo | todo | | |
| 09 | Benchmark & report | todo | | |

## Handoff notes

Append one section per phase: key files, deviations from DECISIONS.md,
open issues, anything the next phase must know.

### Phase 01

- Backend: Python 3.14 uv project, installable package `app`
  (hatchling). `app/config.py` (`Settings`, DSNs typed `PostgresDsn`,
  defaults point at the ephemeral DB on 55432, so no `.env` needed),
  `app/database.py` (`Base`, `_make_engine_url`, cached `get_engine`,
  `get_db` resolving settings via `Depends(get_settings)`),
  `app/errors.py` (`AdrianoError` + Configuration/NotFound/Conflict/
  Forbidden/ValidationFailed errors mapped to HTTP), `app/routers/
  health.py`. Alembic `env.py` reads Settings; `versions/` empty.
- Tests: `tests/conftest.py` provides `test_settings` and `client`
  (override `get_settings`). One harmless Starlette/httpx deprecation
  warning.
- Ruff: line 80, rules E F I D C90 B UP; pydocstyle pep257 with D211/D212
  ignored (opening `"""` alone on its line).
- Taskfile: `task dev` = db:up + migrate + backend (8100) & frontend
  (5173) in parallel. Frontend tasks call npm scripts `lint`,
  `typecheck`, `test`, `build`, `dev`.
- Frontend: Vue 3.5 / Vuetify 4.2 / Vite 8 / vue-router 5 / vitest 5;
  TypeScript pinned to 5.9 (typescript-eslint does not support TS 7).
  `src/api/index.ts` (ApiError, TokenProvider default null,
  unauthorized/success handlers), `src/config.ts` (runtime config,
  `apiBaseUrl` only), composables `useLoading`, `useHealth`, shared
  `EmptyState`/`ErrorState`/`LoadingState`/`StatusChip`, views Search
  (q synced to URL, honest empty state), Record/Sources placeholders,
  NotFound. No `/api/v1` calls yet.
- Verified by coordinator: lint, test (2 backend, 12 frontend), build,
  Playwright smoke (all routes, skip link first in tab order, no console
  errors). Playwright: the MCP browser lacks Chrome; use the scratchpad
  `playwright` package with its bundled chromium headless shell.
- Notes: host inotify limit is near exhaustion (watcher EMFILE warnings
  under `task dev`, servers still work). `npm audit` reports a likely
  stale braces/micromatch advisory; installed braces 3.0.3 is fixed.

### Phase 02

- `backend/app/domain/`: `hashing` (`content_digest`, `Digest`,
  `sha256-v1` / `sha256-raw-v1`), `issues` (`Issue`, `IssueCode`,
  `Severity`, `to_dict/from_dict`), `values` (`RecordKind`, `Links`,
  `Identity`, `record_key`), `titles`, `frontmatter`, `fields`,
  `validation`, `records` (`parse_record(raw, filename=) ->
  ParsedRecord`, re-exports values/titles), `relationships`
  (`RecordSummary`, `RelationshipIndex`, `resolve_relationships`,
  `DisplayStatus`), `approval` (`Policy`, `PolicyStatus`,
  `DecisionEventView`, `evaluate`, `last_decided`, `is_eligible`,
  `is_self_approval`, `principal`).
- Persist `ParsedRecord.display_date` as `decision_date` and
  `decision_date_inferred` as the flag.
- SQL needs-approval must mirror `approval.py` rule order: no policy ->
  policy_missing; required false -> not_required; latest event for the
  current digest -> accepted/rejected; any acceptance of another digest
  -> changed_since_acceptance; else pending. `approvable` only affects
  `can_decide`.
- Deviations: extra issue code `ambiguous_target` (warning);
  `legacy_signoff` is a warning; bad-encoding files parsed with U+FFFD
  replacement (still not approvable, raw digest).
- `RelationshipIndex` expects one summary per row (normally published
  rows); feeding candidates too reports them as duplicates — phase 05
  must decide how candidates participate.
- YAML loader keeps unquoted dates as strings. Only ATX H1 detected.
- 104 domain tests (hypothesis added as dev dep). Pyright in an IDE on
  Python 3.13 flags forward refs; the project targets Python 3.14
  (PEP 649 deferred annotations) — use `backend/.venv`.

### Phase 03

- Port: `app.storage.port` — `CatalogStoreProvider` (`unit_of_work()`,
  `lock_registration(source_id)`: both context managers yielding a
  `CatalogStore`, one transaction, commit on exit) and `CatalogStore`
  (registrations sync/get/list/update_poll_status; revisions put/get;
  `upsert_published`, `upsert_candidate`, `create_candidate`,
  `get_record`, `list_change_tokens`, `delete_published`,
  `list_identity_siblings`, `list_relationship_summaries`;
  `search(query, filters, page, page_size, *, policy)`;
  `append_decision`, `list_decisions`; intake runs start/finish/find).
  Value types in `app/storage/values.py`, re-exported by `port.py`.
- Implementation: `app.storage.postgres.store.PostgresStoreProvider(
  engine)`. Not yet wired into FastAPI: build it at the composition
  root from `get_engine(str(settings.database_url))`.
- Migration `0001_initial`: tables per DECISIONS.md; partial unique
  indexes; trigger-maintained weighted tsvector (simple + english
  body); statement-level append-only trigger on `decision_event`;
  `intake_run.source_id` has no FK (log pushes to unknown ids).
- Errors added: `DecisionExistsError`, `CandidateExistsError`,
  `DeliveryExistsError` (409). Conflicts use ON CONFLICT DO NOTHING so
  the unit of work survives.
- SQL approval state mirrors domain; parity test in
  `tests/storage/test_approval_parity.py`. `NEEDS_APPROVAL_STATES` in
  `postgres/search.py`.
- Code-written timestamps use `clock_timestamp()`.
- Polling (phase 04): record `intake_run` / poll status in a separate
  unit of work from the locked ingest transaction, so a rollback does
  not lose the run log.
- `alembic check` reports comment-only diffs (comments live in the
  migration); strip those from future autogenerate output.
- Root `pyrightconfig.json` points editors at `backend/.venv`.
- 158 backend tests (52 storage).
