# Phase 01 — Scaffold and skeleton UI

## Goal

A clean checkout can install, lint, test, and run an empty but
working backend and a Vuetify skeleton UI, using documented `task`
commands and an ephemeral PostgreSQL container.

## Prerequisites

- None (first phase). `phases/` exists, `git init` done.

## Context to read

- `phases/DECISIONS.md` (all), `phases/README.md`.
- `SPEC.md`: "Architecture and persistence", "UI requirements",
  "Legacy application behavior" (`/healthz`).

## Tasks

### Task 1 — Backend, tooling, Taskfile (model: sonnet)

- `backend/` uv project (latest stable Python available; check
  `uv python list`), `pyproject.toml` with: fastapi, uvicorn[standard],
  pydantic-settings, sqlalchemy, psycopg[binary], alembic, pyyaml,
  httpx, pyjwt[crypto], markdown-it-py, nh3. Dev: pytest,
  pytest-asyncio, ruff. Only add what later phases need from this list;
  later phases may `uv add` more when required.
- Ruff config: line-length 80, rules incl. `E`, `F`, `I`, `D` (sphinx
  style docstrings, per `module-code-style-python`), `C90` (max
  complexity 10), `B`, `UP`.
- `app/config.py` (`Settings`, `ADRIANO_` prefix, `get_settings` cached),
  `app/main.py` `create_app()` factory, `app/errors.py`,
  `app/database.py` (engine/session factory, `_make_engine_url`
  injecting `+psycopg`, `get_db` dependency), `app/routers/health.py`
  with `GET /healthz` returning `{"status": "ok"|"degraded",
  "database": "ok"|"unavailable"}` (HTTP 200 / 503).
- Alembic initialised (`backend/alembic/`, `env.py` reading Settings).
  No migration revisions yet (phase 03 creates 0001).
- `backend/tests/conftest.py`: test settings from
  `ADRIANO_TEST_DATABASE_URL`; a test for `/healthz` (DB up) and one for
  the 503 path (bad DSN override).
- Root `Taskfile.yml` (go-task v3) with tasks:
  - `db:up`: `docker run -d --rm --name adriano-db -p 55432:5432
    --tmpfs /var/lib/postgresql -e POSTGRES_USER=adriano
    -e POSTGRES_PASSWORD=adriano -e POSTGRES_DB=adriano postgres:<latest
    stable major tag>`; idempotent (no-op if running); wait for
    `pg_isready`; create `adriano_test`. No volumes.
  - `db:down`, `db:reset` (down + up), `migrate` (alembic upgrade head
    on dev DB).
  - `dev:backend` (uvicorn reload on port 8100), `dev:frontend`
    (vite on 5173).
  - `lint` (ruff check + ruff format --check + frontend lint/typecheck),
    `test` (pytest + vitest), `build` (frontend build).
  - Placeholders are **not** allowed: add `poll`, `mint-dev-token`,
    `demo`, `bench` only in the phase that implements them.
  - Tasks load `.env` if present (`dotenv: ['.env']`).
- `.env.example` documenting every Settings field (dev values point at
  port 55432; no secrets), `.gitignore` (.env, .env.local, .venv,
  node_modules, dist, __pycache__, screenshots of demo excluded only if
  large).
- `catalog.example.yaml` as in DECISIONS.md (it is loaded only from
  phase 04 on; keep it documented with comments).
- `.devcontainer/devcontainer.json` + `.devcontainer/init.bash`
  (`uv sync`, `npm ci`), per `stack-fastapi-vuetify` "Dev container".
  Forward 8100, 5173, 55432.
- Update `CLAUDE.md`: append a short "UI route" note: Vuetify, chosen
  via the `stack-fastapi-vuetify` kit (one line of reasoning). Do not
  remove existing content.
- `README.md` quickstart: prerequisites (uv, node, docker, task),
  `task db:up`, `task migrate`, `task dev:backend`, `task dev:frontend`,
  `task test`.

### Task 2 — Frontend skeleton (model: sonnet)

- `frontend/` Vite + Vue 3 + Vuetify 4 (latest) + TypeScript +
  vue-router + vitest + eslint/vue-tsc. `.ts`/`.vue` only under `src/`.
- `src/api/index.ts`: fetch-based `api.get/post/put/delete`, `ApiError
  {status, data}`, `setUnauthorizedHandler`, `setAuthSuccessHandler`,
  `TokenProvider` + `setTokenProvider` (default provider returns `null`
  — real tokens arrive in phase 06; do not use localStorage for tokens).
- `src/config.ts`: typed runtime config reading `window.__APP_CONFIG__`
  with `import.meta.env.VITE_*` fallback (`module-runtime-config-spa`);
  `public/config.js` dev stub. Only `apiBaseUrl` for now.
- App shell (`App.vue`): `v-app`, `v-app-bar` with product name,
  navigation (Catalog, Sources), a backend status indicator (icon +
  text, from `/healthz`, re-checked on focus), and the mandatory
  `v-progress-linear` (absolute, bottom, indeterminate, primary) bound
  to a global loading composable.
- Views: `SearchView` (landing; prominent labelled search field that
  writes `q` to the URL query; shows an explicit empty state explaining
  that the catalog has no indexed records yet — **no fake data**),
  `RecordView` and `SourcesView` placeholders with honest "not available
  yet" empty states, `NotFoundView`.
- Shared components: `EmptyState`, `ErrorState` (message + retry
  button), `LoadingState`, `StatusChip` (icon + text, never colour
  alone).
- `src/types/health.ts` for the health payload.
- Vite dev proxy: `/api` and `/healthz` -> `http://localhost:8100`.
- Tests under `frontend/tests/` mirroring `src/`: api client (ApiError,
  401 handler, token header), config fallback, health composable.
- Keyboard: skip-to-content link, visible focus, labelled controls.

## Acceptance criteria touched

1 (partial: clean-checkout start), 4 (skeleton states), 27 (partial:
health endpoint).

## Verification (coordinator)

```
task db:up
cd backend && uv sync && cd ..
(cd frontend && npm ci)
task lint
task test
task build
task dev:backend &   task dev:frontend &
curl -fsS localhost:8100/healthz
```

Then a Playwright smoke check of `/`, `/sources`, a 404 route, with
screenshots saved under the scratchpad (not committed).

## Definition of done

All verification commands green; README quickstart works verbatim;
STATUS.md updated by the coordinator.
