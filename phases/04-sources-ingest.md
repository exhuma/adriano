# Phase 04 — Configuration, sources, ingest, polling

## Goal

`catalog.yaml` drives source registrations and the approval policy.
Both source types (filesystem, GitLab) feed one shared ingest path.
`adriano poll` polls all enabled registrations with reconciliation and
recorded outcomes.

## Prerequisites

- Phases 01–03 `done`.

## Context to read

- `phases/DECISIONS.md`: "Configuration", "Sources", "Persistence".
- `SPEC.md`: "Source registrations and intake", "Architecture and
  persistence", acceptance criteria 5–11.

## Tasks

### Task 1 — Catalog configuration loader (model: opus)

- `app/catalog_config.py`: pydantic models for `sources`,
  `approval_policy`, `rbac`; load from `ADRIANO_CONFIG_FILE`. Per-entry
  validation: an invalid registration is disabled with a readable
  `config_error`; invalid/missing policy -> `PolicyStatus.missing` or
  `.invalid` with message (never "not required"). Secrets resolved from
  env var names; values never logged or stored in DB `config`.
- Startup sync into `source_registration` (via store), in the app
  lifespan and in the CLI.
- `adriano check-config` CLI command (entry point in `pyproject.toml`):
  prints registrations, policy status, and problems; non-zero exit on
  errors.
- Tests for valid/invalid configs, secret redaction.

### Task 2 — Source port, ingest service, polling, CLI (model: opus)

- `app/sources/port.py`: `SourceAdapter` Protocol with
  `async list_projects()`, `async list_documents(project, previous_tokens)`
  returning listings with change tokens and a `complete` flag,
  `async fetch(document)` returning bytes + source URL + author; plus
  `SourceError` types. Provider-neutral types only.
- `app/sources/registry.py`: type -> factory; validates type-specific
  config at the adapter boundary.
- `app/services/ingest.py`: **the** shared path used by poll and push:
  parse (domain) -> validate -> digest -> `put revision` -> render
  Markdown with markdown-it-py and sanitize with nh3 -> upsert record
  (published or candidate) -> record issues. Relationship issues
  (`missing_target`, `duplicate_uuid`) are computed at read time or in
  a post-ingest pass over the registration; choose one and document it.
  Ingest never touches `decision_event`.
- `app/services/polling.py`: per registration, under the advisory lock:
  record `intake_run`, apply ownership rule, skip unchanged change
  tokens (no fetch), fetch changed ones with bounded concurrency, ingest,
  reconcile deletions only for projects whose listing was complete and
  only when the project listing was complete; set
  `last_attempt_at/last_success_at/last_status/last_error`. A failure in
  one registration never affects others.
- `adriano poll [--source ID]` CLI; add `task poll`.

### Task 3 — Filesystem adapter (model: sonnet)

- `app/sources/filesystem.py` per DECISIONS.md. Change token
  `mtime_ns:size`. `file://`-free source URL: expose a display path.
  Unreadable root -> `SourceError` (poll fails, nothing deleted).
- Tests with `tmp_path`: discovery regex + recursion, unchanged files not
  re-read (spy), deletion reconcile, unreadable root preserves records.

### Task 4 — GitLab adapter (model: opus)

- `app/sources/gitlab.py` per DECISIONS.md using `httpx.AsyncClient`
  (verify=True, timeouts, limits), keyset/offset pagination via `Link`
  / `X-Next-Page`, semaphore-bounded blob fetches, retries with
  backoff on 429/5xx (honour `Retry-After`), `@project-default`
  resolution, branch-head short-circuit, archived projects excluded,
  author from last commit of the file only if cheaply available (else
  `None`; document).
- Tests with `httpx.MockTransport` only (no network): pagination, blob
  skip on unchanged `blob_id`, branch-head skip, 5xx retry then success,
  persistent failure -> partial run without deletions, token never in
  logs (caplog), archived project removal on complete listing.

## Acceptance criteria touched

6, 8, 9, 10, 11, 23 (end-to-end through ingest).

## Verification (coordinator)

```
task db:reset && task migrate
task lint && task test
ADRIANO_CONFIG_FILE=catalog.example.yaml uv run adriano check-config
```

Plus a manual poll of a small temporary filesystem tree into the dev DB
(the full sample tree arrives in phase 08).

## Definition of done

Green checks; poll and push (phase 07) can both call
`services/ingest.py`; no GitLab-specific code outside `gitlab.py`.
