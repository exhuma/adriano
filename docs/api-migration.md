# API migration from the legacy application

Audience: developers/operators who ran the previous `ADR_VIEWER_`-
configured service and need to know what changed. See
`phases/SPEC.md` "Legacy application behavior" for the full
description of the old behaviour this is migrated from.

## Route changes

| Legacy route | Legacy behaviour | Replacement |
|---|---|---|
| `GET /` | Redirected to `/docs`. | Redirects to the SPA's search landing page (`/`, served by the frontend). API documentation moved to `/api/docs` (see below). |
| `GET /adr/` | Returned HTML by default; JSON when `Accept: application/json` or `?json=true` was given; **scraped its configured source on every request**. | Replaced entirely by `GET /api/v1/records` (search/list) and `GET /api/v1/records/{id}` (detail), both JSON-only, both served from the local index -- **no source call happens on a normal read** (acceptance criterion 5). There is no HTML-vs-JSON content negotiation: the SPA renders the HTML view client-side from the JSON API. |
| `GET /healthz` | DB-independent liveness check. | **Preserved at the same path**, now reporting `{status, database, config, policy, registrations, auth, rbac}` -- still public, still no record data or secrets. |
| `GET /docs` | FastAPI's interactive API docs. | Moved to `GET /api/docs` (OpenAPI schema at `GET /openapi.json`); both public, both contain no record data. |

The most significant behavioural change is **not having `/adr/`
scrape its source on each request**. The old service doubled as a
source adapter and a web view in one request; the new service always
serves from its own index, and a separate, explicit operation
(polling, or CI push) is what talks to a source (acceptance criteria
5, 6, 8).

## Configuration migration (`ADR_VIEWER_*` -> adriano)

The old deployment configured its source with `ADR_VIEWER_`-prefixed
environment variables. The replacement uses a product-neutral model:
one `catalog.yaml` file for sources/policy/rbac (`ADRIANO_CONFIG_FILE`
points at it), plus `ADRIANO_`-prefixed environment variables for
everything else (database, auth, dev bypass). There is no 1:1
variable rename -- the shape changed from "one source, env-configured"
to "any number of named source registrations, file-configured" -- but
every piece of information the old variables carried has a new home:

| What the old `ADR_VIEWER_*` variable configured | New configuration |
|---|---|
| Which repository/path to scrape | A `sources[]` entry in `catalog.yaml` (`type: gitlab` or `filesystem`, `scope`, `path`). See `catalog.example.yaml`. |
| Source credentials | An env var **name** in that entry's `token_env` (GitLab) or none (filesystem), resolved at startup; the value itself is a plain environment variable, never written into `catalog.yaml`. |
| Which branch/ref was considered authoritative | `published_ref` on the source entry (an explicit branch name, or `"@project-default"` for GitLab). |
| SSO/JWT audience (`adr_viewer`) | `ADRIANO_OIDC_AUDIENCE` (same default value, `adr_viewer`, so an existing IdP client registration using that audience keeps working unchanged). |
| Roles file (`roles.toml`), `admin` role -> `read` | `rbac.roles` in `catalog.yaml`, e.g. `admin: [read, operate]` -- the new model adds the separate `operate` permission (triggering polls) and a wholly separate reviewer grant (`approval_policy.reviewers`) that the old service had no equivalent of, since it had no approval workflow at all. |
| Development auth fixture (`dev-auth.toml`, `Admin User` -> `admin`) | `ADRIANO_DEV_AUTH_ENABLED` / `ADRIANO_DEV_SHARED_SECRET` plus `adriano mint-dev-token --sub ... --roles admin`; see `docs/operator.md` "Dev auth must be unset in production". |
| Container entrypoint (5 Uvicorn workers) | `ADRIANO_WORKERS` (default **4**, not 5 -- see `backend/Dockerfile`; override it if your traffic needs more). |

There is no automatic config converter: an operator migrating from the
old deployment writes a new `catalog.yaml` by hand, using
`catalog.example.yaml` as the template and `adriano check-config` to
validate it before pointing production traffic at it.
