# Status

Statuses: `todo`, `in-progress`, `done`, `blocked`.

| # | Phase | Status | Commit | Notes |
|---|---|---|---|---|
| 00 | Planning + phases folder | done | | spec copied, decisions recorded |
| 01 | Scaffold + skeleton UI | done | fcef2ad + next | see notes |
| 02 | Domain core | todo | | |
| 03 | Persistence | todo | | |
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
