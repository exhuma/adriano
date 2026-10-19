# adriano

An ADR (architecture decision record) governance catalog: a FastAPI
backend and a Vue 3 / Vuetify frontend that index ADRs from GitLab
and filesystem sources, track candidate vs. published state, and
enforce a reviewer approval workflow.

See `phases/SPEC.md` for the full product specification and
`phases/DECISIONS.md` for the confirmed architecture and API
contract. This repository is being built phase by phase; see
`phases/STATUS.md` for current progress.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python package/dependency
  manager; it installs the required Python version itself).
- [Node.js](https://nodejs.org/) (for the frontend, once scaffolded).
- [Docker](https://www.docker.com/) (for the ephemeral dev/test
  database).
- [`go-task`](https://taskfile.dev/) v3 (the `task` CLI).

## Quickstart

```sh
# Start the ephemeral dev/test Postgres container (host port 55432;
# no-op if it's already running). Leave it running across sessions;
# `task db:down` discards it.
task db:up

# Install backend dependencies.
cd backend && uv sync && cd ..

# Apply database migrations (no-op until phase 03 adds the first
# revision).
task migrate

# One-command alternative: starts the DB, applies migrations, then
# runs the backend (8100) and frontend (5173) dev servers together.
# Ctrl-C stops both servers; the DB keeps running until `task db:down`.
task dev

# Or run each dev server by hand, in separate terminals:
task dev:backend   # backend, reload, port 8100
task dev:frontend  # frontend, port 5173 (skips gracefully with a
                   # clear message until the frontend exists)

# Lint and test everything.
task lint
task test
```

Once the backend is running, `curl -fsS localhost:8100/healthz`
should return `{"status": "ok", "database": "ok"}`.

## Configuration

Copy `.env.example` to `.env` and adjust as needed; the defaults
already point at the ephemeral dev database on port 55432. See
`.env.example` for every supported `ADRIANO_`-prefixed setting.

The catalog's sources and approval policy are configured in
`catalog.yaml` (see the documented `catalog.example.yaml`). This file
is not read until later phases wire up source polling.

## Project layout

- `backend/` — FastAPI application (`uv` project).
- `frontend/` — Vue 3 / Vuetify 4 / TypeScript application (added in
  a later phase).
- `phases/` — the implementation plan, decisions, and status for
  this build.
- `Taskfile.yml` — all developer commands (`task --list-all`).
- `.devcontainer/` — VS Code dev container configuration.
