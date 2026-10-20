# Decisions and architecture contract

These decisions were confirmed with the product owner on 2026-10-19.
`SPEC.md` remains the source of truth for requirements. This file fixes
the choices the spec left open.

## Confirmed decisions

- **Scope:** Product Phase 1 only. Stop for user review afterwards.
- **Stack:** FastAPI (Python, uv) backend + Vue 3 / Vuetify 4 /
  TypeScript / Vite frontend (quartermaster `stack-fastapi-vuetify`;
  Vuetify route is recorded in `CLAUDE.md`).
- **Auth:** standard OIDC resource server. The backend validates RS256
  bearer tokens with PyJWT against the IdP discovery document / JWKS
  (`module-auth-oidc-python`). Issuer, audience (`adr_viewer` by default)
  and roles claim path are configuration. The SPA is a **public client**
  with Authorization Code + PKCE via `oidc-client-ts`, tokens in memory
  (`module-auth-oidc-vue`). A dev-only HS256 bypass follows
  `module-dev-auth-bypass` (two independent gates, both off by default).
- **Database:** PostgreSQL via psycopg3 + SQLAlchemy 2 + Alembic.
  Search uses a weighted `tsvector` column with a GIN index.
- **Dev/test database:** an ephemeral container started by
  `task db:up` (no volume; `--tmpfs` data dir; `--rm`), host port
  **55432**, user/password `adriano`/`adriano`, databases `adriano` and
  `adriano_test`. `task db:down` discards everything.
- **Ports:** host port 8000 is already used on the dev machine. The dev
  backend runs on **8100**, the Vite dev server on **5173** (proxying
  `/api` and `/healthz` to 8100). Container-internal ports stay
  backend 8000 / frontend 80.
- **Source types in Phase 1:** `gitlab` (required by the spec) and
  `filesystem` (an on-disk folder; authorized by the product owner as a
  deviation so the product can be demoed without an external system).
- **UI grows with the core:** phase 01 ships a Vuetify skeleton (app
  shell, navigation, search landing page, record and sources routes,
  shared loading/empty/error components). Later phases add UI only for
  capabilities the backend provides at that point. Never build UI
  against endpoints that do not exist yet.
- **Execution:** linear sub-agent workflow in the main working tree;
  no git worktrees (see `README.md`).
- **Polling schedule:** external job (`adriano poll` CLI, cron or k8s
  CronJob). No timers inside web workers. Operators can also trigger a
  poll through an authenticated endpoint that calls the same service.

## Repository layout

```
Taskfile.yml            dev tasks (db:up/down/reset, migrate, dev:*, lint,
                        test, build, poll, mint-dev-token, demo, bench)
docker-compose.yml      deploy stack: db, migrate (one-shot), backend,
                        frontend (nginx)
catalog.example.yaml    documented example configuration
.env.example            documented env vars (no secrets)
.devcontainer/          devcontainer.json + init.bash
backend/
  pyproject.toml, uv.lock, alembic.ini, alembic/
  app/
    main.py             create_app(); routers, handlers, dev-auth mount
    config.py           Settings (pydantic-settings, env prefix ADRIANO_)
    catalog_config.py   load + validate catalog.yaml (sources, policy, rbac)
    errors.py           domain exceptions + handler registration
    domain/             PURE: no I/O, no FastAPI, no SQLAlchemy
      hashing.py        canonical digest
      records.py        frontmatter parse, validation, title derivation
      relationships.py  link resolution, reverse errata, derived status
      approval.py       approval-state evaluation
    sources/
      port.py           SourceAdapter Protocol + value types
      filesystem.py     on-disk folder adapter
      gitlab.py         GitLab adapter (only GitLab-specific code here)
      registry.py       source type -> adapter factory + config validation
    storage/
      port.py           CatalogStore Protocol (DB-neutral)
      postgres/         models.py, store.py
    services/
      ingest.py         THE shared parse->validate->hash->persist->index
      polling.py        poll orchestration + reconciliation + run log
      intake.py         CI push (PUT/POST candidates)
      catalog.py        search / detail assembly (read-only, no sources)
      decisions.py      accept/reject + policy enforcement
      diff.py           unified diff between stored snapshots
    auth/               oidc.py, dev.py, deps.py, rbac.py
    routers/            health, records, candidates, decisions, sources,
                        me, auth_dev (mounted only when enabled)
    cli.py              `adriano` CLI: poll, mint-dev-token,
                        seed-synthetic, check-config
  tests/
frontend/
  src/ api/ auth/ composables/ types/ views/ components/ plugins/
  tests/ (mirrors src/)
samples/adr-root/       demo folder tree for the filesystem source
docs/                   schema.md, examples/, hashing.md, approval.md,
                        operator.md, api-migration.md, architecture.md,
                        benchmark.md, phase1-report.md
```

Normal browse/search requests go only through `services/{search,record_detail,record_relationships}.py` and
the store. Source adapters are constructed only by `services/polling.py`
(and intake never calls adapters). A test must prove that read routes
never construct or call an adapter.

## Configuration

Environment (`Settings`, prefix `ADRIANO_`):

- `ADRIANO_DATABASE_URL` — plain `postgresql://` DSN (the `+psycopg`
  modifier is injected in code).
- `ADRIANO_TEST_DATABASE_URL` — used only by tests.
- `ADRIANO_CONFIG_FILE` — path to `catalog.yaml`.
- `ADRIANO_OIDC_AUTHORITY`, `ADRIANO_OIDC_ISSUER`,
  `ADRIANO_OIDC_AUDIENCE` (default `adr_viewer`),
  `ADRIANO_OIDC_ROLES_CLAIM` (dotted path, default `roles`).
- `ADRIANO_DEV_AUTH_ENABLED`, `ADRIANO_DEV_SHARED_SECRET` — dev only,
  unset in production, no default secret.
- Secrets referenced from `catalog.yaml` (GitLab tokens, CI push tokens)
  are env var **names**, resolved at startup and never logged.

`catalog.yaml` (one file, read at startup; changes need a restart):

```yaml
sources:
  - id: central                 # stable registration id
    type: filesystem            # filesystem | gitlab
    root: ./samples/adr-root    # filesystem only
    scope: {projects: [platform, payments]}   # optional filter
    path: doc/decisions         # ADR path inside each project
    published_ref: local        # explicit label/branch; required
    intake: [poll, push]
    push_tokens_env: [ADRIANO_PUSH_TOKEN_CENTRAL]
  - id: gitlab-platform
    type: gitlab
    base_url: https://gitlab.example.com
    token_env: ADRIANO_GITLAB_TOKEN_PLATFORM
    scope: {groups: [platform], include_subgroups: true, projects: []}
    path: doc/decisions
    published_ref: "@project-default"   # or a branch name
    intake: [poll, push]
    push_tokens_env: [ADRIANO_PUSH_TOKEN_PLATFORM]
approval_policy:
  id: global
  version: 1
  required: true
  reviewers:
    users: ["https://idp.example.com|subject-123"]   # issuer|subject
    roles: [adr-reviewer]
  allow_self_approval: false
rbac:
  roles:                # IdP role -> permissions
    admin: [read, operate]
    adr-reader: [read]
```

- A missing or invalid `approval_policy` does **not** stop startup. It
  yields the `policy_missing` state everywhere and is reported in
  `/healthz` and the UI. Decisions are refused while it is missing.
- Invalid `sources` entries are reported per registration (`check-config`
  CLI, startup log, `/api/v1/sources`) and that registration is disabled;
  the rest of the catalog keeps working.

## Record schema (documented in docs/schema.md with examples)

```yaml
---
uuid: 0b0c2f4e-...         # required; stable record id
title: Use PostgreSQL      # optional; fallback: first H1, then filename
decision-date: 2024-12-24  # optional; filename date only shown as
                           # "inferred from filename"
kind: decision             # decision (default) | erratum
updates: [<uuid>, ...]     # newer -> earlier decision it updates
obsoletes: [<uuid>, ...]   # replacing -> decision it replaces
corrects: <uuid>           # erratum only -> decision it corrects
deprecates: <uuid>         # LEGACY alias of obsoletes (warning)
signed-off-by: [...]       # LEGACY; "Legacy sign-off (unverified)"
---
Markdown body
```

- Discovery: files under the registration `path` (default
  `doc/decisions/`), recursively, whose filename matches
  `^\d{4}-\d{2}-\d{2}-(.*)\.md$`.
- Validation issues are stored per record as
  `{severity: error|warning, code, message}`. Codes:
  `bad_yaml`, `missing_frontmatter`, `missing_uuid`, `bad_uuid`,
  `bad_date`, `missing_date`, `unknown_field`, `bad_field_type`,
  `duplicate_uuid`, `missing_target`, `legacy_alias`,
  `legacy_signoff`, `corrects_on_non_erratum`, `erratum_without_target`,
  `bad_encoding`.
- A record without a valid UUID is still stored, keyed by
  `src:<source_id>/<project>/<path>`. Its UUID-based relationships are
  disabled and the issue is reported. No UUID is invented.
- Display status is derived from links only ("Obsoleted by …",
  "Updated by …"). Errata for a decision are found by reverse lookup of
  `corrects`. No standalone status field.

## Canonical content hash (`sha256-v1`)

Digest string: `sha256-v1:<64 lowercase hex>`. Input:

1. The exact bytes fetched or pushed.
2. Decode as strict UTF-8 (failure -> `bad_encoding` error; the record is
   still stored with the digest of the raw bytes under
   `sha256-raw-v1:` and cannot be approved).
3. Remove one leading U+FEFF (BOM).
4. Replace CRLF with LF, then any remaining lone CR with LF.
5. Encode as UTF-8 and hash with SHA-256.

No path, ref, commit, project, or registration id enters the hash. The
digest identifies a content revision only; it proves neither authorship
nor publication nor that persistence rows were not tampered with
(documented in docs/hashing.md; tamper evidence is deferred).

## Persistence

Alembic migration 0001 creates:

- `source_registration` — `id` (config id), `type`, `config` JSONB
  (secrets excluded), `enabled`, `config_error`, `last_attempt_at`,
  `last_success_at`, `last_status`
  (`never|ok|partial|failed|disabled`), `last_error` JSONB.
  Synced from `catalog.yaml` at startup; registrations removed from the
  config are marked disabled, never deleted.
- `revision` — `digest` PK, `content` text, `created_at`. Immutable,
  content-addressed snapshot store used for diffs and approval evidence.
- `record` — surrogate `id` (uuid, used in URLs), `kind`
  (`published|candidate`), `source_id`, `project`, `path`, `ref`,
  `adr_uuid` (nullable), `record_key` (uuid string or fallback key),
  `digest` FK revision, `previous_digest`, `change_token`, `metadata`
  JSONB (parsed frontmatter), `title`, `title_source`
  (`frontmatter|h1|filename`), `decision_date`, `decision_date_inferred`
  bool, `record_kind` (`decision|erratum`), `links` JSONB, `rendered_html`
  (sanitized with nh3 at ingest), `issues` JSONB, `source_url`, `author`,
  `search` tsvector (weights: title A; uuid/project/path B; body C),
  `first_seen_at`, `updated_at`, `last_seen_at`.
  Unique: published `(source_id, project, path)` (partial index where
  kind = published); candidate `(source_id, project, record_key, ref)`
  (partial index where kind = candidate). Indexes named explicitly.
- `decision_event` — `id` uuid, identity `(source_id, project,
  record_key)`, `adr_uuid`, `digest`, `action` (`accepted|rejected`),
  `actor_issuer`, `actor_subject`, `actor_display`, `actor_email`,
  `comment`, `policy_id`, `policy_version`, `provenance` JSONB (record
  id, kind, ref, path, source_url at decision time), `created_at`
  (server `now()`). **UNIQUE (source_id, project, record_key, digest)**:
  one formal decision per content hash. Triggers raise on UPDATE,
  DELETE, and TRUNCATE (append-only; migrations 0001 + 0002).
- `intake_run` — `id`, `source_id`, `kind` (`poll|push`),
  `identity` JSONB, `delivery_id` (unique with source_id when set),
  `started_at`, `finished_at`, `status`, `counts` JSONB, `errors` JSONB.

Concurrency: writes for one registration take
`pg_advisory_xact_lock(hash(source_id))`; upserts use `ON CONFLICT`;
decision races resolve via the unique constraint (HTTP 409). Safe with
multiple replicas and workers.

The `storage/port.py` Protocol is the only thing services depend on.

## Approval semantics

Logical identity = `(source_id, project, record_key)`. State of a
record's **current digest** (pure function in `domain/approval.py`):

| State | Condition | Needs approval |
|---|---|---|
| `policy_missing` | policy absent or invalid | yes |
| `not_required` | policy `required: false` | no |
| `accepted` | accepted event for (identity, digest) | no |
| `rejected` | rejected event for (identity, digest) | yes |
| `changed_since_acceptance` | an accepted event exists for the identity but another digest | yes |
| `pending` | otherwise | yes |

- Records with an `error`-severity identity problem (no valid UUID, bad
  encoding) cannot be approved; they show `pending` with the reason.
- UI labels: "Accepted — candidate" / "Accepted — published" (state
  `accepted` + record kind), plus branch/ref provenance.
- **Promotion is implicit:** decisions are keyed by identity + digest, so
  a published record with the same identity and digest as an accepted
  candidate is accepted with the full history. Nothing is copied.
- **Divergence:** if the published digest differs from an accepted
  candidate's digest, both rows stay; the published one shows
  `changed_since_acceptance` (or `pending`) and links to the candidate.
- **Competing candidates:** several candidates of one identity on
  different refs are separate rows with independent states; the detail
  page lists them with a warning. A decision on one never affects
  another digest.
- The same UUID in a different project or registration is a different
  identity, flagged `duplicate_uuid`. Promotion never crosses projects.
- Eligibility: the caller's `issuer|subject` is in `reviewers.users`, or
  one of the caller's roles is in `reviewers.roles`. Read permission
  never implies review.
- Self-approval (when `allow_self_approval: false`): refused when the
  reviewer's verified email equals the record `author`. `author` comes
  from the push request or GitLab commit author; filesystem records have
  none (documented limitation).
- Diff default: last decided (accepted, else rejected) snapshot of the
  identity -> current; else the record's `previous_digest` -> current;
  else "no prior revision".

## Sources

Common registration fields: `id`, `type`, `scope`, `path`,
`published_ref`, `intake` (`poll`, `push`, or both), `push_tokens_env`.

- **Ownership:** the first registration in config order that yields a
  `(project, path)` owns it; later registrations skip it and log an
  `ownership_conflict` warning in their poll run.
- **filesystem:** `root` directory; each immediate subdirectory is a
  project (filtered by `scope.projects` when given). Change token =
  `mtime_ns:size`; unchanged files are not re-read. A complete walk
  reconciles deletions and vanished project directories. An unreadable
  root fails the poll and deletes nothing.
- **gitlab:** `base_url`, `token_env`,
  `scope {groups, include_subgroups, projects}`,
  `published_ref: <branch> | "@project-default"`. Steps: paginated
  non-archived project listing for the scoped groups/projects; branch
  head per project (unchanged -> skip project); paginated recursive tree
  under `path`; fetch raw blobs only when `blob_id` changed; bounded
  concurrency (semaphore), httpx timeouts, retry with backoff on 429/5xx,
  TLS verification on, token in `PRIVATE-TOKEN` header, never logged.
  A complete listing reconciles deleted files and archived/removed
  projects. Partial/failed polls delete nothing for the affected scope.
- The port exposes provider-neutral types only (project id/path, file
  path, change token, content bytes, source URL, author, ref). Push
  intake does not call the adapter.

## HTTP API (`/api/v1`; OpenAPI UI at `/api/docs`)

- `GET /healthz` — DB ping plus config/policy status. Container
  healthcheck.
- `GET /api/v1/records?q=&source=&project=&state=candidate|published&needs_approval=true&page=&page_size=`
  — bounded pagination (max 50).
- `GET /api/v1/records/{id}` — detail: metadata, issues, rendered HTML,
  provenance, freshness, outbound/inbound links, errata, sibling
  revisions (published/candidates of the same identity), approval state,
  history, policy summary.
- `GET /api/v1/records/{id}/diff?from=&to=` — unified diff between stored
  snapshots, with both digests labelled.
- `POST /api/v1/records/{id}/decisions` `{action, comment}` — eligible
  reviewers only; 403 with reason; 409 if (identity, digest) decided.
- `PUT /api/v1/candidates` (idempotent create/replace) and
  `POST /api/v1/candidates` (409 if the candidate identity exists). Body:
  `{source_id, project, adr_uuid, ref, content, path?, delivery_id?,
  author?}` (`path` defaults to `<registration path>/<adr_uuid>.md`).
  Auth: bearer push token of that registration (constant-time compare).
  Checks: registration has `push` intake, project within scope, ref is
  not the published ref, document UUID equals `adr_uuid`. 422 with the
  issue list for unparseable/mismatched documents. Any client-supplied
  digest is ignored; the response returns the server digest.
- `GET /api/v1/sources`; `POST /api/v1/sources/poll`;
  `POST /api/v1/sources/{id}/poll` (operate permission).
- `GET /api/v1/me` — identity, permissions, reviewer eligibility.
- `/` and SPA routes are served by the frontend; `/adr/` is gone
  (docs/api-migration.md maps old behaviour and `ADR_VIEWER_` config).

## Frontend end state (built up phase by phase)

- Search landing page: search field (primary), source/project select,
  candidate/published/all toggle, "Needs approval" switch, "Clear
  filters"; all in URL query params; compact paginated results (title,
  source/project, state chip, approval chip, issue indicator).
- Record page: rendered (sanitized) Markdown, metadata, validation
  issues, provenance + source link, freshness and stale/failed banner
  ("last indexed …; may not be the current published revision"),
  approval card (state, policy summary, history, Accept/Reject dialog
  with comment for eligible reviewers), diff panel (both hashes),
  outbound/inbound links, errata, competing candidates, "Legacy sign-off
  (unverified)".
- Sources page: per-registration status and freshness; "Poll now" for
  operators.
- Every status uses icon + text (never colour alone); deliberate
  loading, empty, error+retry, success and stale states; keyboard
  operable; labelled controls; `v-progress-linear` at the bottom of the
  app bar for page loads.
- Runtime config via `config.js` rendered by the nginx entrypoint
  (`module-runtime-config-spa`); dev auth never in runtime config.

## Authorized post-Phase-1 change (2026-10-20)

The product owner authorized, after reviewing Phase 1, a record-page redesign
(status banners at the top, metadata in a sidebar, modelled on
rfc-editor.org/info pages) and a dedicated erratum format replacing the
`kind: erratum` + `corrects:` ADR shape. See `phases/10-ui-errata.md`. Errata
are separate files with `erratum-for`, `type`, optional `section`/
`reported-by`/`date`, and body sections "Original text", "Corrected text",
"Notes"; their status reuses accept/reject (Reported / Verified / Rejected).
The old shape is rejected with `legacy_erratum_format`.

**Phase 10 updates:**
- `kind: decision` now gives an `obsolete_kind_field` warning. Only
  `kind: erratum` + `corrects` are legacy-format errors; plain decisions
  do not fail validation.
- Facets count decisions only, matching the default search filter
  (record_type = decision).
- A published erratum under a `required: false` policy counts as
  "verified or not requiring review" in the summary.
- Candidate errata count only as "proposed" (pending_count in summary).

## Deferred (do not build)

Admin/config UI, webhooks, more source types, quorum/multi-stage review,
notifications, revocation, graph views, cycle analysis, date/lifecycle
facets, identity-conflict remediation, tamper-evident audit export, LLM
features.
