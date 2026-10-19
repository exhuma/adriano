# Phase 08 — Samples, deployment, documentation, demo

## Goal

The product runs from a clean checkout in containers, ships realistic
sample data, has operator/user documentation, and the full Phase 1
workflow is demonstrated with screenshots.

## Prerequisites

- Phases 01–07 `done`.

## Context to read

- `phases/DECISIONS.md` (all).
- `SPEC.md`: "Phase 1 delivery and handoff", criteria 1, 27.
- quartermaster `stack-fastapi-vuetify` (deployment),
  `module-runtime-config-spa`, `module-documentation`.

## Tasks

### Task 1 — Samples, containers, docs (model: sonnet)

- `samples/adr-root/` with at least two projects plus a `central`
  project: legacy files (`uuid`, `decision-date`, `signed-off-by`,
  `deprecates`), new-schema files (`title`, `kind`, `updates`,
  `obsoletes`), an erratum, an invalid-YAML file, a bad-UUID file, a
  duplicate UUID across projects, a broken link. Also `samples/candidates/`
  with files for the push demo.
- `docs/examples/` mirror of schema examples.
- `backend/Dockerfile` and `frontend/Dockerfile` (multi-stage, latest
  stable base tags), `frontend/nginx.conf` (SPA fallback, `/api` and
  `/healthz` proxy), entrypoint rendering `config.js` from env.
- `docker-compose.yml`: `db` (named volume), `migrate` (one-shot,
  `alembic upgrade head`), `backend` (uvicorn, workers from env,
  healthcheck on `/healthz`, depends on migrate completion), `frontend`.
  Samples mounted read-only for the filesystem source. Required env
  documented in `.env.example`.
- `task demo` (bring up compose with dev auth enabled for local demo
  only, run poll) and `task demo:down`.
- Docs: `docs/schema.md`, `docs/hashing.md` (algorithm + limits),
  `docs/approval.md` (policy, states, promotion, divergence, competing
  candidates, self-approval limits), `docs/operator.md` (config file,
  secrets, TLS, GitLab token scopes (`read_api` + `read_repository`),
  push token setup, CI example `curl`/GitLab CI job, polling schedule
  via cron/CronJob, health checks, backup `pg_dump`/restore, retention
  of decision events and revisions, migrations, multi-replica notes,
  troubleshooting), `docs/api-migration.md` (`/adr/` and
  `ADR_VIEWER_` mapping), `docs/architecture.md` (concern map, data
  flow, storage choice), README update.

### Task 2 — End-to-end demo (model: sonnet)

- Using `task demo` (or dev servers), drive with Playwright and capture
  screenshots under `docs/demo/` (small PNGs):
  1. search landing, filters, results;
  2. detail of a legacy record (legacy sign-off unverified, legacy
     alias warning, links);
  3. invalid record isolated with issues;
  4. CI `curl -X PUT` candidate -> visible as candidate, pending;
  5. reviewer accepts -> "Accepted — candidate";
  6. identical file copied into the sample tree, poll -> "Accepted —
     published", same digest, same history;
  7. file edited, poll -> "changed since acceptance", diff view,
     needs-approval filter;
  8. reject flow on another candidate;
  9. source failure (rename root / unreadable) -> poll failed, stale
     banner, records still browsable; recovery after fixing.
- Write `docs/demo/README.md` narrating the steps and commands. Restore
  sample files afterwards (git checkout).

## Acceptance criteria touched

1, 2, 3, 4, 27 and demonstrations of 12, 13, 20, 21.

## Verification (coordinator)

```
task lint && task test && task build
docker compose build && task demo
curl -fsS localhost:<frontend port>/healthz
```

Review the screenshots.

## Definition of done

Clean-checkout container start works with documented commands; demo
narrative and screenshots committed.
