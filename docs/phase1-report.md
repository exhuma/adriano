# Phase 1 acceptance report

Audience: the product owner (go/no-go decision) and architects reviewing
fit and risk. Dated 2026-10-19, covering the state of the repository at
commit `f154ddf`. See `phases/SPEC.md` ("Phase 1 acceptance", "Phase 1
delivery and handoff") for the requirements this report answers against,
and `phases/DECISIONS.md` for the confirmed architecture.

An independent, read-only audit of all 27 acceptance criteria ran before
this report. It found 23 criteria passing outright, 3 partial (clean
checkout quickstart; raw-JSON error text on the Sources page; OIDC
deployment blockers in the CSP and in empty optional settings), and one
not measured because the auditor was not permitted to run the benchmark
(its recorded numbers already met the target). Three commits
(`c0e831c`, `22386ae`, `f154ddf`) fixed every partial finding. This
report is an independent re-verification against the current code and
test suite, not a restatement of the audit; every status below was
checked again against the repository as it stands today.

## 1. Summary

Phase 1 delivers a working ADR governance catalog: a FastAPI backend
and a Vue 3 / Vuetify frontend that index Markdown ADRs from GitLab and
filesystem sources, keep candidate and published content separate, and
enforce a single global reviewer approval policy bound to a content
hash, independent of branch or commit.

**How to run it.**

```sh
cp .env.example .env            # dev-auth settings; see README "Quickstart"
cp catalog.demo.yaml catalog.yaml
cd backend && uv sync && cd ..
task dev                        # DB + backend (8100) + frontend (5173)
task poll                       # index samples/adr-root/
```

For the full containerised demo instead:

```sh
task demo       # build + start + first poll; frontend at :8180
task demo:ui    # second terminal: interactive dev sign-in at :5180
task demo:down  # stop and discard the stack
```

`docs/demo/README.md` walks through every acceptance criterion with
screenshots, using the demo stack above.

**Re-verification performed for this report** (current checkout,
commit `f154ddf`):

| Command | Result |
|---|---|
| `task lint` | ruff check/format clean; eslint 0 warnings; `vue-tsc --build` clean |
| `task test` | 426 backend tests passed; 151 frontend tests (21 files) passed |
| `task build` | frontend production build succeeds; dev-login check passes |
| `cd backend && uvx pyright app tests` | 0 errors, 0 warnings |

`task demo` and `task bench` were intentionally **not** run for this
report, per instruction; criterion 25 below cites the team's own
recorded `docs/benchmark.md` results instead of a fresh run.

## 2. Acceptance criteria

All 27 criteria pass. None are downgraded from the pre-fix audit's
post-fix expectation; the three criteria the audit found partial (1,
3, 26) were re-checked directly against the fix commits and now pass.

| # | Criterion (short) | Status | Evidence |
|---|---|---|---|
| 1 | Clean-checkout quickstart works | PASS | `Taskfile.yml` `dev` → `frontend:install` (auto `npm ci`) + `db:up` + `migrate`; `RESOLVE_CONFIG` resolves `ADRIANO_CONFIG_FILE` to an absolute path from the repo root regardless of task `dir:`; `README.md` "Quickstart"; `task lint/test/build` all green this session |
| 2 | First-time users understand state unaided | PASS | `docs/demo/README.md` steps 1-4; `StatusChip`, `utils/labels.ts`, `utils/freshness.ts` wording |
| 3 | Clear status/recovery on failures, invalid input, decisions | PASS | `frontend/src/utils/sourceErrors.ts` ("Never falls back to raw JSON", audit finding fixed); `tests/routers/approval/test_candidates.py` (422/413/403/401 with reasons); `app/services/decisions.py` `decision_blocker`; demo step 12 "Problem & recovery" column |
| 4 | Keyboard-operable, responsive, deliberate UI states | PASS | Phase 01 Playwright smoke (skip link, no console errors); `de80b34` collapsible app bar; `docs/demo/README.md` step 13 (390px); 151 frontend tests |
| 5 | Normal requests never call a source | PASS | `tests/routers/test_no_adapter_calls.py::test_every_read_route_never_constructs_an_adapter` (patches every adapter constructor to raise; covers search/filter/needs-approval/detail/diff/sources/facets/me) |
| 6 | Polling scans only configured published/default refs | PASS | `app/services/polling.py`; `tests/services/test_filesystem_polling.py`, `test_gitlab_polling.py`; `published_ref` per registration (`phases/DECISIONS.md` "Sources") |
| 7 | Operator poll trigger; authenticated CI push | PASS | `app/routers/sources.py` (`operate` permission); `tests/routers/test_poll_trigger.py`; `app/auth/push.py` + `tests/routers/approval/test_candidates.py` (token scoping) |
| 8 | Poll and push share one pipeline | PASS | `app/services/ingest.py` `prepare_document`/`ingest_document` used by both `polling.py` and `intake.py`; `docs/architecture.md` poll/push sequence diagrams |
| 9 | Unchanged content is not refetched/reprocessed | PASS | `test_second_poll_does_not_read_unchanged_files`; `test_polls_ingest_then_skip_unchanged_branches`; `test_moved_head_fetches_only_changed_blobs` |
| 10 | Source failure preserves prior content, reports status | PASS | `test_missing_root_fails_the_poll_and_keeps_records`; `test_persistent_failure_is_partial_and_deletes_nothing`; `test_failed_group_listing_deletes_nothing`; demo step 12 |
| 11 | Complete poll reconciles deletions; partial does not | PASS | `test_complete_poll_deletes_removed_files_and_projects`; `test_archived_project_is_removed_on_a_complete_listing` (vs. the partial/failed tests above) |
| 12 | Candidate intake never overwrites published | PASS | `test_candidate_never_overwrites_published`; partial unique indexes keyed by `kind` (`phases/DECISIONS.md` "Persistence") |
| 13 | Identical promoted content keeps hash/history | PASS | `test_identical_content_is_accepted_when_published`; `docs/hashing.md` test vector 2 (same digest candidate → published); demo steps 7-8 |
| 14 | Legacy `uuid`/`decision-date`/`signed-off-by`/`deprecates` readable | PASS | `samples/adr-root/` legacy files; `tests/domain/test_records.py` (44+ tests); demo step 3 |
| 15 | Legacy sign-off never counts as approval | PASS | `app/domain/approval.py` `evaluate()` has no `signed-off-by` input; UI label "Legacy sign-off (unverified)"; `docs/approval.md` "Self-approval and its limits" |
| 16 | Global policy documented/configured/enforced; persists | PASS | `catalog.yaml` `approval_policy`; `decision_event` is a Postgres table (not in-memory), survives restart by construction; `tests/storage/test_approval_parity.py`; `tests/routers/approval/test_decisions.py` |
| 17 | Digest reproducible across refs/encodings | PASS | `docs/hashing.md` test vector 1 (CRLF/BOM invariance); `test_line_endings_and_bom_do_not_change_digest`; `test_digest_depends_only_on_bytes` |
| 18 | Edited content invalidates old approval, keeps history | PASS | `test_content_edit_changes_digest`; `test_edited_content_needs_new_approval_and_diffs`; `changed_since_acceptance` state |
| 19 | "Needs approval" covers unmet/rejected/changed/unconfigured | PASS | `test_needs_approval_filter_across_states`; `tests/storage/test_approval_parity.py` (SQL/domain parity across policy variants) |
| 20 | UI diff from last approved snapshot, no Git needed | PASS | `app/services/diff.py`; `frontend/src/components/DiffPanel.vue`; `test_candidate_diff_uses_previous_revision`; demo step 8b |
| 21 | Stale/failed poll never claims currency | PASS | `frontend/src/utils/freshness.ts` `freshnessBannerText` (no banner for candidates/push-only; distinct wording for failed vs. merely stale); demo step 12c |
| 22 | Decisions identify policy; append-only history | PASS | `decision_event` columns `policy_id`/`policy_version`; migrations `0001_initial` (UPDATE/DELETE trigger) + `0002_no_truncate_decisions` (TRUNCATE trigger); `docs/operator.md` "Database role and tamper resistance" |
| 23 | Bad metadata affects only its own record | PASS | Demo step 4 (`bad_yaml` isolated, 14 other records unaffected); `tests/domain/test_records.py` validation-issue tests |
| 24 | Legacy `deprecates` and typed links navigable | PASS | Demo step 3 (`deprecates` resolves and is clickable); `frontend/src/components/record/RecordLinksCard.vue`; `app/domain/relationships.py` |
| 25 | P95 target met or gap measured | PASS (measured) | `docs/benchmark.md`: worst observed p95 is 269.7 ms (`needs_approval`, 20,000 records, concurrency 8), well under the 1 s target; synthetic dataset, limitations stated below |
| 26 | SSO/RBAC protects access, approvals, polling, push | PASS (enforcement; see limitation) | `tests/routers/test_auth.py` 401/503 sweep over every `/api/v1` operation, RS256 via a fake IdP; `tests/routers/test_permissions.py`; push-token scoping in `tests/routers/approval/test_candidates.py`; CSP and empty-setting fixes in `c0e831c` (see "Deviations" and "Known limitations") |
| 27 | Health checks, persistence, backup/restore documented | PASS | `docs/operator.md` "Health checks", "Backup and restore", "Migrations", "Retention"; `backend/Dockerfile`/`frontend/Dockerfile` `HEALTHCHECK` |

### Note on criterion 26

Backend enforcement is fully exercised by tests: every `/api/v1`
operation rejects an unauthenticated caller, RBAC permission checks and
reviewer eligibility (including self-approval refusal) are tested, and
push tokens are scoped to one registration and one write operation.
RS256 token validation is tested against a fake IdP's JWKS, which
exercises the same validation code path a real IdP would. What was
**not** tested is the browser's live Authorization Code + PKCE redirect
against a real external IdP (none was available in this environment),
and RP-initiated logout is not implemented. Judgement: this gap affects
whether a user can complete sign-in through a specific real provider
(an availability/UX question, covered under criteria 1-2's operator
guidance), not whether the catalog, once a valid token exists, is
protected — the backend rejects missing/invalid/expired/wrong-audience
tokens unconditionally regardless of how the token was obtained. The
criterion is therefore reported as passing, with the untested round
trip and missing logout named explicitly under "Known limitations"
rather than hidden.

## 3. Performance

### Measured p95, by scenario, dataset size, and concurrency

All values in milliseconds, from `docs/benchmark.md` (dataset, method,
and full p50/p99/max tables there; `docs/bench-2000.json` and
`docs/bench-20000.json` hold the raw output).

| Scenario | 2k, conc 1 | 2k, conc 8 | 20k, conc 1 | 20k, conc 8 |
|---|---|---|---|---|
| free_text | 19.5 | 89.6 | 57.9 | 134.1 |
| filtered | 14.1 | 90.4 | 15.7 | 81.9 |
| needs_approval | 26.5 | 109.4 | 114.1 | 269.7 |
| detail | 18.4 | 98.3 | 41.4 | 96.9 |
| sources | 7.0 | 53.2 | 7.2 | 42.7 |

Every cell is under the 1-second P95 target; the worst is 269.7 ms
(`needs_approval`, 20,000 records, concurrency 8).

**Environment:** Intel Core Ultra 5 125U (14 logical CPUs), 15 GiB RAM,
Ubuntu 25.10 / Linux 6.17.0-41-generic, Python 3.14.4, PostgreSQL 18.6
in the ephemeral `task db:up` container (`--tmpfs` data directory, so
the database lives in RAM, not disk), backend as `uvicorn --workers 4`
on the host, client (`backend/bench/bench.py`, httpx) on the same host
(no network hop). 400 requests per scenario per concurrency after 50
warm-up requests, at concurrency 1 and 8.

**Dataset and limitations:** synthetic ADR corpus generated by
`adriano seed-synthetic` and ingested through the same
`prepare_document`/`ingest_document` path poll and push use (never raw
SQL), seed 42, 2,000 and 20,000 published records over 100 projects.
Titles/bodies are templated, not organic prose, so full-text relevance
*ranking quality* is not representative, only its latency; there is one
registration and one source type (`filesystem`), so this does not
measure multi-registration contention or the `gitlab` adapter; decision
history is flat (no multi-round accept/reject sequences); body text is
English-only ASCII. A `--tmpfs` database and a same-host client are
both faster than a typical production deployment; a real deployment
with network separation and disk-backed storage will see additional,
unmeasured latency. Treat the *shape* of the results (which scenario is
slow, and why) as the evidence to extrapolate from, not the exact
millisecond values.

### Two optimisations applied

1. **Record detail targeted fetch.** `GET /api/v1/records/{id}`
   originally built its relationship index from *every* published row
   on every request (~780 ms at 20,000 records, almost entirely Python
   row marshalling, not the database). A new, targeted query
   (`list_relationship_candidates`) fetches only the rows that can
   possibly affect one record's view — same UUID, its own link
   targets, or rows linking back to it — cutting the cost to ~18 ms
   (about 40x). A dedicated test
   (`test_relationship_candidates_match_the_full_index_view`) proves
   the targeted fetch computes the identical view as the full fetch.

2. **The `needs_approval` filter.** This filter originally cost p95
   1.85 s (concurrency 1) and 4.16 s (concurrency 8) at 20,000 records:
   a correlated-subquery `CASE` expression per row drove PostgreSQL's
   cost estimate above its JIT thresholds, adding 0.4-0.8 s of JIT
   compilation per statement on top of the per-row probes. Rewriting it
   as set-based joins (`approval_join`) dropped it to 114.1 ms /
   269.7 ms (about 16x), with no schema change; `test_approval_parity.py`
   proves the SQL state matches the pure-function domain rule for every
   row under every policy variant.

## 4. Demo summary

`docs/demo/README.md` is a 13-step, screenshotted walk-through of the
containerised demo stack (`task demo` / `task demo:ui`), each step
naming the acceptance criteria it demonstrates: search and filtering
(1-2), a legacy record (3), an isolated invalid record (4), a CI push
candidate (5), a reviewer's accept with the exact digest shown (6),
identical-content promotion (7), an edit breaking acceptance with a
diff (8), the "Needs approval" filter (9), a rejection with a comment
(10), a read-only reader's view (11), operator polling and a source
failure with recovery (12), and the mobile layout (13). Three preset
identities (Reader, Reviewer, Operator/Admin) exercise every RBAC path
without a real IdP.

## 5. Deviations and recorded design choices

**Deviations authorized by the product owner** (`phases/DECISIONS.md`):

- **Filesystem source type.** The spec names `gitlab` as the required
  source type; `filesystem` (an on-disk folder, same adapter protocol)
  was added so the product can be demonstrated end to end without
  standing up a real GitLab instance.
- **Ephemeral dev database via Taskfile.** `task db:up` runs a
  no-volume, `--tmpfs` Postgres container; `task db:down` discards it.
- **Sub-agent workflow.** Implementation ran as a linear sequence of
  sub-agents in the main working tree (no git worktrees), coordinated
  and verified by the main session per `phases/README.md`.
- **Commit signing disabled locally.** `git config --local
  commit.gpgsign false`, because the GPG pinentry cannot be answered
  unattended in this environment; author identity is still set
  explicitly on every commit.

**Other recorded design choices** (left open by the spec, fixed in
`phases/DECISIONS.md`/code):

- Error responses are a flat `{detail, code}` body with a stable
  machine `code` for every 401/403/409/422/503.
- List pagination uses `page`/`page_size` query parameters (max page
  size 50), not cursor-based paging.
- `PUT`/`POST /api/v1/candidates` accepts an optional `path`, defaulting
  to `<registration path>/<adr_uuid>.md` when omitted
  (`app/services/intake_checks.py`).
- `ADRIANO_WORKERS` defaults to 4 in the backend container
  (`backend/Dockerfile`), matching the benchmark environment.
- Fixed ports: dev backend 8100, dev frontend (Vite) 5173, demo stack
  frontend 8180, demo interactive dev sign-in 5180 — chosen because
  host port 8000 is already in use on the reference dev machine.
- Tokens are kept in memory only (no `localStorage`/cookie); a full
  page reload signs the user out. This is a deliberate choice to avoid
  persisting a bearer token in browser storage, traded against the
  inconvenience of losing a session on reload.

## 6. Known limitations

- **OIDC round trip and logout.** The full browser Authorization
  Code + PKCE flow was never exercised against a real external IdP (one
  was not available in this environment); RP-initiated logout is not
  implemented. See the criterion 26 note above.
- **CSP and single-origin IdP.** The frontend's Content-Security-Policy
  allows exactly one additional origin (`OIDC_AUTHORITY`'s own origin)
  in `connect-src`/`frame-src`. An IdP whose discovery document points
  token/JWKS/authorize endpoints at a *different* origin than the
  authority is blocked by the browser; there is no setting to add
  extra allowed origins.
- **IPv6 IdP hosts rejected.** The entrypoint's `OIDC_AUTHORITY`
  validation pattern accepts a DNS name or IPv4 literal host, not a
  bracketed IPv6 literal (`https://[::1]:8443`); such a host is
  refused at container start with "not a valid URL".
- **Self-approval check has no author for polled records.** `author`
  is only known for CI-pushed candidates that supplied it, or GitLab
  commit authors; filesystem-polled records have no author concept, so
  the self-approval refusal cannot block a filesystem-sourced record.
  Documented in `docs/approval.md` "Self-approval and its limits".
- **Only the literal `published_ref` is refused on push.** A
  registration configured with `published_ref: "@project-default"`
  does not call the adapter during push intake, so a candidate pushed
  to whatever the project's actual default branch happens to be is not
  specially recognised and refused the way a literal branch name is.
- **Genuine duplicate UUIDs do not block approval.** Two published
  files sharing one UUID are shown as a `duplicate_uuid` error on the
  record detail page, but this does not prevent a reviewer from
  deciding either row; only missing-UUID and bad-encoding identity
  problems block approval.
- **No rate limiting on push intake.** Every `PUT`/`POST
  /api/v1/candidates` request writes an `intake_run` row, including
  unauthenticated or invalid ones; there is no rate limit, so a
  misbehaving or malicious caller can grow this table without being
  slowed down.
- **Delivery-id deduplication ignores content.** A repeated
  `delivery_id` short-circuits to the earlier result regardless of
  whether the request body actually matches; it is a retry-safety
  mechanism, not a content check.
- **Candidates of other identities do not participate in relationship
  resolution.** The detail page's relationship index is built from
  published rows plus the viewed record's own identity siblings;
  a candidate of a *different* ADR identity is never considered as a
  link target or source.
- **Search list items carry no derived display status.** The
  lifecycle-derived status ("Obsoleted by…", "Updated by…") is computed
  only on the record detail page, not in search results.
- **Benchmark dataset is synthetic.** See "Performance" above for the
  specific limitations of the generated corpus.
- **Plain `docker compose up` after a restart drops the demo push
  token.** The demo stack's backend reads secrets from
  `ADRIANO_BACKEND_ENV_FILE=.env.demo`; restarting with a bare `docker
  compose up` (no env-file override) recreates the backend without the
  demo push token. `task demo:poll`/`task demo:down`/`task demo` set
  this correctly; a manual restart must repeat
  `ADRIANO_BACKEND_ENV_FILE=.env.demo docker compose up -d`.
- **Compose database password defaults to `adriano`.** The `db`
  service falls back to this password when `ADRIANO_DB_PASSWORD` is
  unset. The database port is not published outside the compose
  network, but any real deployment should still set a strong password
  or point at a managed PostgreSQL instance.
- **Three frontend views exceed the ~150-line component-size target**
  from the structural code-quality kit: `RecordView.vue` (279 lines,
  already split into 7 sub-components under
  `frontend/src/components/record/`), `SearchView.vue` (407 lines),
  and `SourcesView.vue` (361 lines). Further decomposition was not done
  in Phase 1 to avoid expanding scope at the end of the work.
- **Append-only decision history is not tamper-evident against a
  privileged attacker.** The database triggers added in migrations
  `0001`/`0002` stop application bugs and ordinary mistakes (UPDATE,
  DELETE, TRUNCATE), not a table owner or superuser, who can disable or
  drop the trigger. `docs/operator.md` documents running the
  application as a non-owner role with no `TRUNCATE`/`ALTER` grant as
  a stronger, still not cryptographic, mitigation.

## 7. Deferred backlog (not implemented)

From `phases/SPEC.md` "Later-scope backlog" and `phases/DECISIONS.md`
"Deferred", plus items raised while doing this work:

- Additional source types, webhooks, and event-driven intake.
- Source-registration and approval-policy administration UI.
- Multi-stage/quorum approval, notifications, and revocation workflows.
- Advanced lifecycle graph views, cycle analysis, and date/lifecycle
  search facets.
- Optional local LLM assistance (semantic search, suggested links).
- Identity-conflict remediation tooling (for records with no valid
  UUID or duplicate UUIDs).
- **Tamper-evident audit export** — a signed, periodic export of
  `decision_event` rows to protected, write-once storage, proposed in
  `docs/hashing.md` "Deferred: tamper evidence for the audit trail" as
  the scoped answer if the append-only trigger's limits (see "Known
  limitations") become unacceptable.
- **`count(*) OVER ()` for the `needs_approval` query** — measured in
  `docs/benchmark.md` at roughly 45-55 ms against ~70 ms for the
  current two-statement form; not adopted because the extra single-
  statement complexity (a separate count path for pages past the end)
  was not justified once the target was met with large headroom.
- **An additional-IdP-origins setting** — raised while fixing the CSP
  audit finding: today the CSP allows exactly the configured
  `OIDC_AUTHORITY` origin; an IdP that serves token/JWKS/authorize
  endpoints from a second origin needs a new setting to list it, not
  implemented in Phase 1.
- **RP-initiated logout** — the frontend clears its in-memory token on
  sign-out but does not redirect to the IdP's end-session endpoint, so
  the IdP's own session (and silent-renew iframe) may remain active.

## 8. Review gate

Work stops here. No Phase 2 or later-scope item has been started. This
report, the demo (`docs/demo/README.md`), and the measured latency
above are presented for explicit product-owner review before any
further work begins.
