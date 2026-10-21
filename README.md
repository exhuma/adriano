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
- [Node.js](https://nodejs.org/) (for the frontend).
- [Docker](https://www.docker.com/) (for the ephemeral dev/test
  database).
- [`go-task`](https://taskfile.dev/) v3 (the `task` CLI).

## Quickstart

```sh
# Copy the documented env file and fill in the dev-only settings
# (see "Authentication" below; both must stay unset in production).
cp .env.example .env
# Edit .env and set:
#   ADRIANO_DEV_AUTH_ENABLED=true
#   ADRIANO_DEV_SHARED_SECRET=<paste the output below>
#   VITE_DEV_AUTH=true
openssl rand -hex 32

# Copy the bundled demo catalog so there is a configured `catalog.yaml`
# to poll. Its `root: ./samples/adr-root` is resolved relative to the
# config file's own directory, so it still resolves once copied here
# (both land at the repository root).
cp catalog.demo.yaml catalog.yaml

# Install backend dependencies.
cd backend && uv sync && cd ..

# Start the ephemeral dev/test Postgres container (host port 55432;
# no-op if it's already running), apply migrations, then run the
# backend (8100) and frontend (5173) dev servers together. Ctrl-C
# stops both servers; the DB keeps running until `task db:down`.
task dev

# Or run each step by hand, in separate terminals:
task db:up         # start the ephemeral DB (no-op if already running)
task migrate       # apply Alembic migrations
task dev:backend   # backend, reload, port 8100
task dev:frontend  # frontend, port 5173

# In another terminal: index the sample ADRs in samples/adr-root.
task poll

# Lint and test everything.
task lint
task test
```

Open <http://localhost:5173> and use the "Dev sign-in" chip to sign in
as one of the preset identities (Reader, Reviewer, Operator) -- no
external identity provider needed. The presets are derived from the
loaded `catalog.yaml` roles (with the local example: `adr-reader`;
`adr-reader, adr-reviewer`; `admin`); presets the catalog cannot
satisfy are hidden, and roles can always be typed by hand. Once the
backend is running,
`curl -fsS localhost:8100/healthz` should return
`{"status": "ok", "database": "ok", "config": "ok", "policy": "configured", "registrations": "synced", "rbac": "configured", "auth": "dev"}`.

For the fully containerised stack instead (no dev servers, built
images, `task poll` run for you), see "Running in containers" below.

## Running in containers (Docker Compose)

For a one-command local demo with sample ADR data, dev sign-in, and
the full containerised stack (db, migrations, backend, frontend):

```sh
task demo         # build + start + poll + print URLs and sign-in help
task demo:poll    # re-poll the demo stack later
task demo:down    # stop and discard the demo stack
```

The demo stack publishes the frontend on **<http://localhost:8180>**
(host ports 8000/8080 are commonly already in use; see
`docs/operator.md`). The frontend container is a *production* build
with no dev-login UI; run `task demo:ui` in another terminal for an
interactive sign-in (a Vite dev server with dev login, proxying to
the same demo backend), or mint a token on the command line:

```sh
docker compose exec backend adriano mint-dev-token --sub alice --roles admin
```

For a non-demo deployment, see `docs/operator.md` "Install and run";
it covers `docker compose build && docker compose up -d` against your
own `catalog.yaml` and `.env`, with no dev auth and a real OIDC
provider.

## Reading a record page

Opening any decision or erratum from search shows:

- **Status banners** at the top: "This decision is obsolete, see
  ...", "This decision was updated, see ...", "This decision has N
  errata (...)", or, on an erratum's own page, "This is an erratum
  for <decision>" plus its own status (Reported / Verified /
  Rejected / Changed since verification).
- **The document** itself in the main column: the rendered decision
  text, or, for an erratum, its type/section line followed by
  labelled "Original text (says)", "Corrected text (should say)" and
  "Notes" blocks.
- An **"About this decision"** (or "About this erratum") sidebar with
  everything that is not the document itself: an approval summary
  chip linking to the full approval history, the UUID, decision
  date/provenance/freshness, links to other decisions, sibling
  revisions, and any legacy sign-off.
- An **errata section** lower in the main column, listing every
  erratum reported against the decision with its status, type,
  section, and the original/corrected text, each linking to its own
  page.

Search has a **"Show"** filter (Decisions / Errata / Both) next to
the Published/Candidate toggle, so you can include or focus on
errata.

## Configuration

Copy `.env.example` to `.env` and adjust as needed; the defaults
already point at the ephemeral dev database on port 55432. See
`.env.example` for every supported `ADRIANO_`-prefixed setting.

The catalog's sources, approval policy and role permissions (`rbac`)
are configured in `catalog.yaml` (see the documented
`catalog.example.yaml`); validate it with `task check-config`.

### Authentication

Every `/api/v1` route needs an `Authorization: Bearer` token; only
`/healthz` and the API docs (`/api/docs`, `/openapi.json`, which
contain no data) are public. In production the backend validates
RS256 tokens from your OIDC provider (`ADRIANO_OIDC_AUTHORITY`,
`ADRIANO_OIDC_ISSUER`, `ADRIANO_OIDC_AUDIENCE`,
`ADRIANO_OIDC_ROLES_CLAIM`). Roles map to `read` / `operate` through
the `rbac` section of `catalog.yaml`.

To run locally without an identity provider, enable the dev-only
HS256 path in your (gitignored) `.env`:

```sh
ADRIANO_DEV_AUTH_ENABLED=true
ADRIANO_DEV_SHARED_SECRET=<output of `openssl rand -hex 32`>
```

Then mint a token for any identity and call the API:

```sh
TOKEN=$(task mint-dev-token -- --sub alice --name Alice --roles admin)
curl -H "Authorization: Bearer $TOKEN" localhost:8100/api/v1/me
```

`ADRIANO_DEV_AUTH_ENABLED=true` also mounts `POST /auth/dev/token`
(body `{"sub", "name", "email", "roles"}`) and `GET /auth/dev/roles`
(the catalog's `rbac` roles with their permissions and the approval
policy's reviewer roles, used for the sign-in presets) for the
frontend dev login.
Never set either variable in production; the backend logs a warning
at startup whenever the dev path is active.

## Documentation

- `docs/schema.md` -- the ADR Markdown/frontmatter schema and legacy
  compatibility.
- `docs/hashing.md` -- the canonical content-hash algorithm and its
  limits.
- `docs/approval.md` -- the approval policy, states, and review
  workflow.
- `docs/operator.md` -- install, configure, run, back up, and
  troubleshoot a deployment.
- `docs/api-migration.md` -- mapping from the legacy `/adr/` service
  and its `ADR_VIEWER_*` configuration.
- `docs/architecture.md` -- concern map, data flow, and storage
  choice.
- `docs/benchmark.md` -- the search/browse latency benchmark against
  the Phase 1 P95 target, dataset, environment, and results.
- `docs/examples/README.md` -- pointers into `samples/adr-root/` for
  every schema/validation example.
- `docs/phase1-report.md` -- the Phase 1 acceptance report: criteria
  status, measured latency, deviations, known limitations, and the
  deferred backlog.

## Project layout

- `backend/` — FastAPI application (`uv` project).
- `frontend/` — Vue 3 / Vuetify 4 / TypeScript application (Vite).
- `samples/adr-root/` — sample ADR tree for the bundled `filesystem`
  source (legacy and current schema, errata, and every validation
  issue, see `docs/examples/README.md`).
- `samples/candidates/` + `samples/push-candidate.sh` — CI push demo
  files and a runnable push script.
- `docker-compose.yml` — the deploy stack (db, migrate, backend,
  frontend); `catalog.demo.yaml` — the demo-only catalog
  configuration (`catalog.example.yaml` is the documented reference).
- `docs/` — schema, hashing, approval, operator, migration, and
  architecture documentation.
- `phases/` — the implementation plan, decisions, and status for
  this build.
- `Taskfile.yml` — all developer commands (`task --list-all`).
- `.devcontainer/` — VS Code dev container configuration.
