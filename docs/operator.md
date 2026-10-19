# Operator guide

Audience: operators installing, configuring, and running adriano.
See `docs/architecture.md` for how the pieces fit together and
`docs/approval.md`/`docs/schema.md` for the catalog/review model.

## Install and run (Docker Compose)

```sh
git clone <repository> && cd adriano
cp .env.example .env            # adjust ADRIANO_DATABASE_URL etc. if
                                 # not using the bundled `db` service
docker compose build
docker compose up -d
docker compose exec backend adriano poll   # first index
curl -fsS http://localhost:8180/healthz
```

This starts, in order: `db` (PostgreSQL 18), `migrate` (applies
Alembic migrations once, then exits), `backend` (FastAPI, only
starts after `migrate` exits successfully), `frontend` (nginx
serving the built SPA, proxying `/api/`, `/healthz`, `/auth/dev/` to
`backend`). The published port is **8180** (host 8000 and 8080 are
commonly already in use; see `docker-compose.yml`). The compose
project is named `adriano` (`name: adriano` in `docker-compose.yml`)
so it never collides with another project on the same Docker host.

For a full local demo with sample data and dev sign-in, use
`task demo` instead -- see `README.md` "Quickstart" and
`docs/demo/README.md`.

## Configuration file and environment reference

Two configuration layers:

1. **Environment variables** (`ADRIANO_`-prefixed; see `.env.example`
   for every one with its default and meaning): database connection,
   OIDC issuer/audience/roles claim, the dev-auth bypass (never set
   in production), and `ADRIANO_CONFIG_FILE` (path to the catalog
   file below).
2. **`catalog.yaml`** (`ADRIANO_CONFIG_FILE`, read once at startup;
   see `catalog.example.yaml` for the fully annotated reference and
   `catalog.demo.yaml` for the smaller demo configuration): source
   registrations, the one global approval policy, and the `rbac` role
   -> permission map.

Validate the catalog file without touching the database:

```sh
docker compose exec backend adriano check-config
```

A problem in `catalog.yaml` never stops the application: an invalid
source registration disables only that registration (with a readable
`config_error`, visible in `check-config`, the startup log, and
`GET /api/v1/sources`); a missing/invalid `approval_policy` disables
decisions everywhere until fixed (see `docs/approval.md`).

## Secrets handling

- Never put a real secret value in `catalog.yaml`. Every secret
  referenced there (GitLab tokens, CI push tokens) is an environment
  variable **name**, resolved once at startup and never logged.
- Never commit `.env` or `.env.demo` (both are gitignored).
- In `docker-compose.yml`, secrets are passed as plain environment
  variables (from `.env` or the shell); there is no secrets-manager
  integration in Phase 1 -- if your platform has one, inject it as
  environment variables at the container level, which `backend`
  already reads.
- The compose `db` service falls back to the password `adriano` when
  `ADRIANO_DB_PASSWORD` is unset. That default is for the local demo
  only (the database port is not published). Set a strong
  `ADRIANO_DB_PASSWORD` for any real deployment, or point
  `ADRIANO_DATABASE_URL` at a managed PostgreSQL instead.

## TLS

- **Inbound:** TLS terminates at your ingress/load balancer in front
  of the `frontend` container; this stack does not run TLS inside the
  containers. Point your ingress at `frontend`'s published port
  (8180 by default) and configure the certificate there.
- **Outbound (GitLab):** the backend always verifies the GitLab
  server's TLS certificate (`httpx` default certificate validation)
  when polling a `gitlab` source. There is no configuration switch to
  disable certificate verification -- use a properly signed
  certificate (or add your internal CA to the container's trust
  store) rather than disabling verification.

## GitLab token scopes and scope configuration

A `gitlab` source registration needs a **personal or project access
token** with:

- `read_api` (to list projects/branches/trees through the REST API),
- `read_repository` (to fetch raw file blobs).

No write scope is ever needed; the backend never writes to GitLab.
Reference the token by env var name in `catalog.yaml`:

```yaml
- id: gitlab-platform
  type: gitlab
  base_url: https://gitlab.example.com
  token_env: ADRIANO_GITLAB_TOKEN_PLATFORM
  scope:
    groups: [platform]
    include_subgroups: true
    projects: []
  path: doc/decisions
  published_ref: "@project-default"
  intake: [poll, push]
  push_tokens_env: [ADRIANO_PUSH_TOKEN_PLATFORM]
```

`scope` must name at least one group or project. `include_subgroups`
also indexes descendant groups' projects. `published_ref` is either
an explicit branch name or `"@project-default"` to follow each
project's own configured default branch.

## Push tokens and the CI push example

Each registration that allows `push` intake has its own list of
bearer tokens (`push_tokens_env`, env var **names**; several names can
point at independently rotatable tokens for the same registration). A
push token authorizes **only** `PUT`/`POST /api/v1/candidates`
against that one registration -- it grants no read access and is
never accepted on any other route.

`curl` example (see `samples/push-candidate.sh` for a complete,
runnable script that builds the JSON body correctly, including
escaping):

```sh
curl -fsS -X PUT https://adriano.example.com/api/v1/candidates \
  -H "Authorization: Bearer $ADRIANO_PUSH_TOKEN_CENTRAL" \
  -H "Content-Type: application/json" \
  -d '{
        "source_id": "central",
        "project": "platform",
        "adr_uuid": "b87a5fc5-a48f-49cb-a029-ac1f7c56c717",
        "ref": "feature/redis-cache",
        "content": "---\nuuid: b87a5fc5-...\n---\n# ...\n"
      }'
```

GitLab CI job snippet:

```yaml
push-adr-candidate:
  stage: review
  rules:
    - if: '$CI_COMMIT_BRANCH != "main"'
  script:
    - |
      python3 - <<'PY'
      import json, os, pathlib, urllib.request

      path = pathlib.Path("doc/decisions/2026-01-05-use-redis-for-caching.md")
      content = path.read_text(encoding="utf-8")
      body = json.dumps({
          "source_id": "central",
          "project": "platform",
          "adr_uuid": "b87a5fc5-a48f-49cb-a029-ac1f7c56c717",
          "ref": os.environ["CI_COMMIT_REF_NAME"],
          "content": content,
          "delivery_id": os.environ["CI_PIPELINE_ID"],
      }).encode("utf-8")
      req = urllib.request.Request(
          "https://adriano.example.com/api/v1/candidates",
          data=body,
          method="PUT",
          headers={
              "Authorization": f"Bearer {os.environ['ADRIANO_PUSH_TOKEN']}",
              "Content-Type": "application/json",
          },
      )
      urllib.request.urlopen(req, timeout=10)
      PY
```

`delivery_id` makes a retried CI job idempotent: a repeated id returns
the earlier result (`deduplicated: true`) instead of re-ingesting.

## Polling schedule

Scheduled indexing is an **external job**, not a timer inside a web
worker (module-twelve-factor "processes"; `phases/DECISIONS.md`
"Polling schedule"). Two equivalent options:

1. **cron**, calling the CLI inside the running backend container:

   ```cron
   */15 * * * * docker compose -f /opt/adriano/docker-compose.yml \
     exec -T backend adriano poll >> /var/log/adriano-poll.log 2>&1
   ```

2. **Kubernetes `CronJob`**, running the same image with `command:
   ["adriano", "poll"]` on a schedule, instead of `exec`-ing into the
   long-running deployment.

Operators can also trigger an immediate poll from the UI ("Poll now"
on the Sources page, operator-only) or the API
(`POST /api/v1/sources/poll` or `.../sources/{id}/poll`, `operate`
permission).

## Health checks

- `GET /healthz` (public, no record data or secrets): reports
  database reachability plus configuration/policy/registration/auth
  status. Both `backend` and `frontend` containers declare a
  `HEALTHCHECK`:
  - `backend`'s healthcheck calls `/healthz` directly with Python's
    `urllib` (no extra `curl` binary needed in the slim runtime
    image).
  - `frontend`'s healthcheck calls its own `/config.js` (nginx
    serving static content), independent of backend health, so a
    backend outage is visible through `/healthz` rather than marking
    the whole frontend container unhealthy too.
  - **Deviation:** the stack kit this project otherwise follows
    treats `HEALTHCHECK` as opt-in, added only by a dedicated
    observability kit. SPEC.md acceptance criterion 27 explicitly
    requires documented container health checks, so both
    `Dockerfile`s add one deliberately; this is a documented, narrow
    exception to that default.
- `docker compose ps` / `docker inspect --format='{{.State.Health.Status}}' <container>`
  report the current health state.

## Logging

Both the backend and the Uvicorn access log write to stdout/stderr
(never to a file inside the container -- module-twelve-factor "logs
as event streams"). Collect them with your container runtime's normal
log driver (`docker compose logs -f backend`, or your platform's log
aggregation). No secret value (tokens, passwords) is ever logged; only
their configured env var *names* appear in diagnostics.

## Backup and restore

- **Backup:** `pg_dump` the `adriano` database on a schedule that
  matches your recovery objective; daily is a reasonable starting
  point for a catalog that changes by commits/pushes rather than by
  continuous writes:

  ```sh
  docker compose exec db pg_dump -U adriano -d adriano \
    --format=custom --file=/tmp/adriano.dump
  docker compose cp db:/tmp/adriano.dump ./adriano-$(date +%F).dump
  ```

- **Restore:**

  ```sh
  docker compose cp ./adriano-2026-10-19.dump db:/tmp/adriano.dump
  docker compose exec db pg_restore -U adriano -d adriano \
    --clean --if-exists /tmp/adriano.dump
  # Then confirm the schema matches the application's expectations:
  docker compose run --rm backend alembic current
  ```

  If `alembic current` does not report the latest head, run
  `docker compose run --rm migrate` (or `... run --rm backend alembic
  upgrade head`) before starting `backend` against the restored data.

## Retention

- **Kept forever:** `decision_event` (the append-only approval
  history) and `revision` (content-addressed snapshots used for
  diffs and approval evidence) are never pruned by the application --
  they are the audit trail.
- **May be pruned:** `intake_run` (poll/push run log) grows without
  bound and carries no approval evidence. There is no built-in pruning
  job in Phase 1; prune it manually when it grows too large:

  ```sql
  DELETE FROM intake_run
  WHERE finished_at IS NOT NULL
    AND finished_at < now() - interval '90 days';
  ```

  Adjust the interval to your own retention policy. Never delete rows
  with `finished_at IS NULL` (a run still in progress).

## Migrations

Deploy order is always **migrations, then application**
(module-database-postgresql): `docker-compose.yml`'s `migrate`
service runs `alembic upgrade head` and must exit successfully
(`service_completed_successfully`) before `backend` starts. Outside
compose, run the same command before starting (or restarting) the
application:

```sh
docker compose run --rm migrate
# or, against a container already built:
docker compose run --rm backend alembic upgrade head
```

The schema is still the single migration `0001_initial`; the faster
"Needs approval" filter (see `docs/benchmark.md`) is a query change
only and adds no migration. It relies on the existing unique
constraint/index `uq_decision_event_identity_digest` (one decision per
identity and digest) both for correctness and for its lookups: do not
drop or replace it manually.

## Multi-replica notes

- `backend` is a stateless, share-nothing process (module-twelve-
  factor "processes"): run as many replicas as you like behind a load
  balancer; nothing is cached in process memory across requests that
  another replica would need.
- Writes for one source registration take a PostgreSQL advisory lock
  (`pg_advisory_xact_lock(hash(source_id))`), so two replicas polling
  (or being asked to poll) the same registration concurrently cannot
  corrupt its state -- one waits for the other's transaction.
- Decision races (two reviewers deciding the same digest at once)
  resolve through the unique `(source_id, project, record_key,
  digest)` constraint: the second request gets `409 already_decided`
  rather than a silent overwrite.
- `migrate` must run exactly once per deployment, before any replica
  of `backend` starts against the new schema -- this is already
  encoded in `docker-compose.yml`'s `depends_on`.

## Authentication configuration

- `ADRIANO_OIDC_AUTHORITY`: the IdP discovery base URL. Setting it
  enables OIDC; the backend fetches
  `<authority>/.well-known/openid-configuration` and the referenced
  JWKS lazily on first use (an unreachable IdP answers `503`, never a
  crash).
- `ADRIANO_OIDC_ISSUER`: expected `iss` claim (defaults to the
  discovery document's own `issuer` when unset).
- `ADRIANO_OIDC_AUDIENCE` (default `adr_viewer`): expected `aud`
  claim.
- `ADRIANO_OIDC_ROLES_CLAIM` (default `roles`): dotted path to the
  roles list inside the verified token, e.g. `realm_access.roles` for
  Keycloak.
- `rbac` in `catalog.yaml` maps each IdP role name (as it appears
  under the roles claim above) to the permissions it grants (`read`,
  `operate`). A role not listed, or a missing/invalid `rbac` section,
  grants **nothing** -- deny by default. Being an approval reviewer
  (`docs/approval.md`) is a *separate* grant via
  `approval_policy.reviewers`, not a permission.

### Dev auth must be unset in production

`ADRIANO_DEV_AUTH_ENABLED` and `ADRIANO_DEV_SHARED_SECRET` are a
development-only HS256 bypass (`module-dev-auth-bypass`). Both MUST
be unset in any production environment:

- the backend logs a warning at startup whenever the dev path is
  active, and `/healthz`'s `auth` field reports `dev` or `oidc+dev`;
- the frontend's dev-login UI is excluded from every production
  build at build time regardless of any runtime configuration (see
  `frontend/scripts/check-no-dev-auth.sh`, run by `npm run build`) --
  there is no environment variable that can turn it on in a deployed
  image;
- `task demo` is the **only** place these are deliberately enabled,
  into a gitignored, randomly generated `.env.demo` that is never
  committed.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/healthz` returns 503 | Database unreachable. | Check `ADRIANO_DATABASE_URL` and that `db` is healthy (`docker compose ps`); confirm migrations ran (`alembic current`). |
| Every `/api/v1` route returns `401 {"code": "not_authenticated"}` with a `WWW-Authenticate` challenge, or `503 {"code": "auth_unconfigured"}` | No bearer token presented (expected -- it is required), or no auth is configured at all. | Pass `Authorization: Bearer <token>`; if `auth_unconfigured`, set `ADRIANO_OIDC_AUTHORITY` or the dev bypass (dev/demo only). |
| `403 {"code": "permission_required"}` | The caller's roles do not map to the needed permission in `rbac`. | Check `check-config`'s "RBAC roles" output; add the role to `catalog.yaml`'s `rbac.roles`. |
| A registered source shows `config_error` / is disabled in `GET /api/v1/sources` | Invalid `catalog.yaml` entry for that registration (bad URL, missing scope, etc.). | `adriano check-config` prints the exact problem per registration. |
| Approval state is `policy_missing` everywhere | `approval_policy` absent or invalid in `catalog.yaml`. | Add a valid `approval_policy` block (see `catalog.example.yaml`) and restart (the catalog file is read once at startup). |
| A record shows a stale/failed banner even though the content "looks right" | The registration's last poll is older than `ADRIANO_STALE_AFTER_MINUTES`, or failed/partial. | Check `GET /api/v1/sources` for `last_status`/`last_error`; trigger a poll; fix the underlying source access problem (credentials, network, filesystem permissions). |
| `PUT /api/v1/candidates` returns `401 invalid_push_token` | Wrong/rotated token, or the registration has no push tokens configured. | Confirm the env var named in `push_tokens_env` is set to the token you are sending; re-check `catalog.yaml`. |
| `docker compose up` hangs with `backend` never starting | `migrate` failed (its exit code was non-zero). | `docker compose logs migrate`; fix the migration/database problem, then `docker compose up -d` again. |
