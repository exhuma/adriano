# Status

Statuses: `todo`, `in-progress`, `done`, `blocked`.

| # | Phase | Status | Commit | Notes |
|---|---|---|---|---|
| 00 | Planning + phases folder | done | | spec copied, decisions recorded |
| 01 | Scaffold + skeleton UI | done | fcef2ad d0d41dc | see notes |
| 02 | Domain core | done | see git log | see notes |
| 03 | Persistence | done | see git log | see notes |
| 04 | Sources & ingest | done | see git log | see notes |
| 05 | Browse slice | done | see git log | see notes |
| 06 | Auth & RBAC slice | done | see git log | see notes |
| 07 | Approval slice | done | see git log | see notes |
| 08 | Samples, deploy, demo | done | see git log | see notes |
| 09 | Benchmark & report | done | 3db7e88 d0ee735 c0e831c 22386ae f154ddf | see notes |
| 10 | UI sidebar + erratum format | in-progress | | post-Phase-1 change authorized by the product owner (2026-10-20) |

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

### Phase 04

- Config: `app/catalog_config.py` (`load_catalog_config`,
  `CatalogConfig` with `file_status`, `sources`, `policy`
  (`PolicyConfig`: status configured/missing/invalid + domain `Policy`),
  `rbac` (`RbacConfig.permissions_for(roles)`, `Permission` read/operate
  — may move to `auth/rbac.py` in phase 06), `get_source(id)`),
  `app/source_config.py` (`SourceRegistration`: `push_tokens`
  SecretStr, `binding`, `pollable`, `intake`, `published_ref`).
- Composition root: `app/composition.py` (`load_catalog`,
  `build_store_provider`, `build_polling_service`, `start_catalog`,
  `get_catalog_runtime`). Only place reading `os.environ` (secret env
  var names). Lifespan syncs registrations; `/healthz` adds `config`,
  `policy`, `registrations` keys.
- Source port `app/sources/port.py`; registry `default_registry()`
  registers `filesystem` and `gitlab` (lazy imports inside the
  function). `SourceBinding.in_scope(project_path)` is what push intake
  (phase 07) must use for the scope check.
- Ingest: `app/services/ingest.py` — `prepare_document(IncomingDocument)
  -> PreparedDocument` (pure), `ingest_document(store, prepared,
  RecordState, *, create_only=False)`. Push intake: prepare, check UUID,
  then ingest as CANDIDATE inside `lock_registration`.
- Relationship issues (`missing_target`, `ambiguous_target`,
  `duplicate_uuid`) are computed at READ time from
  `list_relationship_summaries()` — phase 05 must do this.
- Polling: `PollingService.poll_all()/poll_source(id)` (async; blocking
  DB calls inside — run HTTP-triggered polls in a worker thread).
  Three units of work: run start, locked ingest, run finish/status.
- CLI `adriano poll [--source ID]`, `adriano check-config`; tasks
  `poll`, `check-config`.
- Filesystem adapter: token `mtime_ns:size`; source_url is the absolute
  path; author None.
- GitLab adapter (`gitlab.py`, `gitlab_settings.py`, `gitlab_api.py`):
  https only; scope needs a group or project; token
  `<blob_id>:<head>:<count>:<path_tag>` enables branch-head skip;
  4 attempts with backoff (Retry-After honoured), 4 concurrent
  requests, `follow_redirects=False`, cross-host Link URLs refused;
  author None (self-approval check cannot block polled records).
- Tests: 253 backend; fake adapter `tests/fakes.py`, fake GitLab
  `tests/gitlab_fake.py`. Autouse fixture strips exported
  `ADRIANO_GITLAB_TOKEN*` / `ADRIANO_PUSH_TOKEN*`. pyright 0 errors on
  `app` and `tests`.

### Phase 05

- Read API: `app/services/{search,record_detail,record_relationships}.py`, routers `records`, `sources`,
  `facets`, schemas in `app/schemas/`. `get_store_provider` dependency
  in `app/composition.py` (override in tests). New store method
  `list_facets()`. Setting `ADRIANO_STALE_AFTER_MINUTES` (120).
- Detail relationship index = published rows + the record's identity
  siblings (candidates of other identities do not participate).
  Siblings in the payload exclude the record itself. Building the
  index per detail request is unoptimised — measure in phase 09.
- Search list items carry no derived display status (detail only).
- OpenAPI schema is at `/openapi.json` (docs at `/api/docs`).
- Frontend: `npm run gen:types` regenerates `src/types/openapi.ts`
  (committed, with snapshot `frontend/openapi.json`; recursive
  `JsonValue` hoisted by the script). Business types in
  `src/types/{records,sources,health}.ts`; API wrappers
  `src/api/{records,sources}.ts`; `useSearchQuery` (URL sync, 300 ms
  debounce, clear); label helpers `src/utils/labels.ts`; dates via Intl.
  Views Search/Record/Sources implemented; app bar shows a
  "Configuration issue" chip from `/healthz`.
- Vitest mounts Vuetify: `server.deps.inline: ["vuetify"]`, polyfills
  in `tests/setup.ts`. `SourcesView` uses `shallowRef` (recursive type).
- Search field no longer autofocuses (it stole focus from the skip link).
- Reusable smoke fixture (outside repo):
  `/tmp/claude-1000/smoke-phase05ui/catalog.yaml` + `adr-root/`
  (7 records incl. legacy, obsoleting, erratum, broken link, bad YAML).
- Tests: 272 backend, 48 frontend.

### Phase 06

- Backend: `app/auth/` (`oidc.py` lazy discovery + cached PyJWKClient,
  `dev.py` HS256, `tokens.py` alg routing, `deps.py` `Principal`,
  `get_principal`, `require_permission`, `rbac.py` incl.
  `reviewer_eligibility(policy_config, issuer=, subject=, roles=) ->
  (eligible, reason)` for phase 07). `create_app(settings=None)` mounts
  `/auth/dev/token` only with flag + secret. Errors `{detail, code}`:
  401 not_authenticated/invalid_token/token_expired, 403
  permission_required, 503 auth_unconfigured/auth_unavailable.
- Routes: `/healthz`, docs public; `/api/v1/me` authenticated;
  records/sources/facets need `read`; `POST /api/v1/sources/poll` and
  `/sources/{id}/poll` need `operate` (202 `{accepted, message}`, 404
  unknown_source, 409 not_pollable; runs via BackgroundTasks +
  asyncio.run in a worker thread). Sweep test asserts every
  `/api/v1` operation in OpenAPI returns 401 without a token — new
  phase 07 routes must keep it green (push intake uses its own token
  scheme: adjust the sweep to expect 401 there too).
- Tests: test settings enable dev auth with `TEST_DEV_SECRET`
  (`tests/auth_helpers.py`, also `FakeIdp` for RS256). 330 backend.
- Frontend: `src/auth/{oidc,reauthGuard,devAuth}.ts`,
  `src/composables/{useAuth,useMe}.ts` (`can(permission)`), sign-in /
  blocking screens, `/auth/callback`, DEV LOGIN chip, Poll all / Poll
  now on Sources (operate only). Tokens in memory: a full page reload
  signs out (by design). Dev login is lazy-loaded behind the inline
  build-time literal; `npm run build` runs
  `scripts/check-no-dev-auth.sh`. `config.template.js` documents the
  runtime env vars for phase 08 (API_BASE_URL, OIDC_*). RP-initiated
  logout not implemented; full PKCE round trip untested without a
  real IdP. 84 frontend tests.
- Local dev login: in `.env` set `ADRIANO_DEV_AUTH_ENABLED=true`,
  `ADRIANO_DEV_SHARED_SECRET=<random>`, `VITE_DEV_AUTH=true`; the
  catalog file needs an `rbac` block.

### Phase 07

- Intake: `app/auth/push.py` (constant-time push tokens, separate
  OpenAPI scheme `PushToken`), `app/services/{intake,intake_checks}.py`,
  router `candidates.py`. `PUT|POST /api/v1/candidates` body
  `{source_id, project, adr_uuid, ref, content, path?, delivery_id?,
  author?}` (extra keys 422). Codes: 401 not_authenticated /
  invalid_push_token (also for unknown sources), 413
  payload_too_large / content_too_large, 422 invalid_request /
  published_ref_not_allowed / invalid_document / uuid_mismatch /
  bad_encoding, 403 push_disabled / project_out_of_scope, 409
  candidate_exists. Every request logs an intake_run. Only the literal
  `published_ref` is refused (no adapter call for `@project-default`).
- Decisions: `app/services/decisions.py` (`decision_blocker` shared by
  POST and detail `can_decide`), router `decisions.py`. Codes 404
  record_not_found, 409 policy_missing / approval_not_required /
  not_approvable / digest_changed / already_decided, 403 not_eligible
  / self_approval. `expected_digest` guards against reviewing stale
  content.
- Detail approval block (`app/services/approval_view.py`): history,
  divergence, competing candidates, `can_decide` + blocked code/reason.
  Diff `app/services/diff.py` (`GET /records/{id}/diff`), limited to
  digests related to the identity. `needs_approval=true` search filter.
- `catalog.py` split into `services/search.py`, `record_detail.py`,
  `record_relationships.py`; `sources_view.py` holds sources/facets.
  All modules <= 500 lines.
- Fix: `RecordSummary` carries `published` + `updated_at`; rows of one
  identity are revisions, not duplicates. `duplicate_uuid` is an error
  only for two published paths of one identity, a warning across
  identities. Links resolve to the identity's published row (else the
  newest candidate). Genuine duplicates are shown but do not block
  approval (DECISIONS.md lists only missing UUID / bad encoding as
  blocking) — recorded as a known limitation.
- Frontend: `useDecision` (core) + `DecisionDialog` (adapter),
  `ApprovalCard`, `DecisionHistoryTable`, `DivergenceBanner`,
  `DiffPanel`; Needs approval switch. Types regenerated.
- Smoke fixture `/tmp/claude-1000/smoke-phase05ui/` now has push intake
  (`ADRIANO_PUSH_TOKEN_CENTRAL`), rbac `adr-reviewer: [read]`, and an
  extra published file `2026-10-19-feature-flags.md`.
- Tests: 389 backend, 109 frontend.

### Phase 08

- Containers: `backend/Dockerfile` (uv build, python 3.14 slim,
  non-root, HEALTHCHECK on /healthz, `ADRIANO_WORKERS` default 4, CMD
  only so `docker compose run backend adriano ...` works),
  `frontend/Dockerfile` (nginx-unprivileged on 8080, entrypoint
  `docker-entrypoint.d/40-render-app-config.sh` renders `config.js`,
  `nginx.conf` proxies `/api/`, `/healthz`, `/auth/dev/`; CSP checked).
- `docker-compose.yml` (name `adriano`): db (postgres:18, volume),
  migrate (one-shot), backend (not published), frontend on host 8180.
  DB password defaults to `adriano` for the demo only (documented).
- Demo: `task demo` (generates gitignored `.env.demo`, builds, starts,
  polls), `task demo:ui` (Vite dev login on 5180 proxied to the stack),
  `task demo:poll`, `task demo:down`. `catalog.demo.yaml` points at
  `samples/adr-root` (root relative to the config file).
- Samples: `samples/adr-root/{platform,payments,central}` (15 ADRs +
  ignored README), `samples/candidates/` (redis/kafka/circuit-breakers),
  `samples/push-candidate.sh`. Index in `docs/examples/README.md`.
- Docs: `docs/{schema,hashing,approval,operator,api-migration,
  architecture}.md`; demo walk-through `docs/demo/README.md` with
  screenshots mapped to criteria. Source failure demo: `mv
  samples/adr-root samples/adr-root.bak`, poll, restore.
- Fix: responsive app bar (`AppBarMenu.vue` below md; DEV chip stays
  visible). Tests: 389 backend, 113 frontend.

### Phase 09

- Benchmark tooling: `adriano seed-synthetic` (`app/services/
  seed_synthetic*.py`) ingests a deterministic synthetic corpus
  through `prepare_document`/`ingest_document` (never raw SQL), seed
  42; `backend/bench/bench.py` (httpx, dev token, warm-up, p50/p95/p99/
  max) drives `task bench`/`task bench:seed`. Results, environment,
  and method recorded in `docs/benchmark.md`
  (`docs/bench-2000.json`/`docs/bench-20000.json`). Worst observed
  p95: 269.7 ms (`needs_approval`, 20,000 records, concurrency 8),
  comfortably under the 1 s target.
- Two optimisations found by benchmarking, both behaviour-preserving
  (proven by dedicated tests): the record detail endpoint's
  relationship index now fetches only candidate rows instead of every
  published row (`list_relationship_candidates`, ~40x faster); the
  `needs_approval` filter now uses set-based joins instead of
  per-row correlated subqueries (`approval_join`, ~16x faster, no
  JIT, no migration).
- Independent read-only audit of all 27 criteria (opus, commits
  `3db7e88`/`d0ee735` precede it): 23 pass, 3 partial (criterion 1
  clean-checkout quickstart; criterion 3 raw-JSON source errors;
  criterion 26 OIDC deployment blockers -- CSP missing the IdP origin
  in `connect-src`/`frame-src`, empty `ADRIANO_OIDC_ISSUER` compared
  literally instead of falling back), 1 not measured (criterion 25,
  auditor not allowed to run the benchmark).
- Fixes for every partial finding, in `c0e831c`/`22386ae`/`f154ddf`:
  `Taskfile.yml` auto-installs frontend deps and resolves
  `ADRIANO_CONFIG_FILE` to an absolute path from the repo root;
  `frontend/src/utils/sourceErrors.ts` renders readable source errors
  (never raw JSON) in a responsive `SourcesView` table;
  `frontend/security-headers.conf.template` +
  `docker-entrypoint.d/40-render-app-config.sh` render the validated
  IdP origin into `connect-src`/`frame-src` and are `include`d in
  every nginx `location` (previously missing on HTML responses);
  `app/config.py` `_blank_to_none` treats an empty optional OIDC/dev
  setting as unset; `docker-compose.yml` backend `env_file` passes
  catalog secrets without touching `docker-compose.yml` per
  registration; migration `0002_no_truncate_decisions` blocks
  `TRUNCATE` on `decision_event` (UPDATE/DELETE were already blocked
  by `0001`), plus non-owner DB role guidance in `docs/operator.md`;
  `test_no_adapter_calls.py` strengthened to patch every adapter
  constructor (proven to catch a real read-path regression, not just
  the registry factory); freshness banner wording now varies by
  record kind and intake mode (`utils/freshness.ts`); the full digest
  is shown in `DecisionDialog`; `DiffPanel` header shows source/
  project/ref and last-indexed time; more frontend tests; several
  stale doc claims corrected; `RecordView.vue` split into 7
  sub-components under `components/record/`.
- Report: `docs/phase1-report.md` (criteria table, measured latency,
  demo summary, deviations, known limitations, deferred backlog). All
  27 criteria pass; the audit's three partial findings (1, 3, 26) and
  its not-measured finding (25) are confirmed fixed/passing against
  the current code and a fresh `task lint && task test && task build
  && uvx pyright` run (426 backend tests, 151 frontend tests, 0
  pyright errors).
- Commits: `3db7e88` (seeding/benchmark/detail optimisation),
  `d0ee735` (needs_approval join), `c0e831c` (audit fixes: CSP, empty
  settings, compose env), `22386ae` (readable source errors,
  freshness wording), `f154ddf` (RecordView split).
- Open issues: none blocking. See `docs/phase1-report.md` "Known
  limitations" and "Deferred backlog" for everything deliberately not
  done. **Stop for product-owner review; no Phase 2 work started.**
