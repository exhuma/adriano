# Phase 06 — Auth and RBAC slice

## Goal

Every route except `/healthz` requires an authenticated identity with
the right permission. Operators can trigger polling from the UI. A
gated dev login lets the product run without an IdP.

## Prerequisites

- Phases 01–05 `done`.

## Context to read

- `phases/DECISIONS.md`: "Confirmed decisions" (Auth), "Configuration".
- `SPEC.md`: "Authentication and authorization", criterion 26.
- quartermaster kits: `module-auth-oidc`, `module-auth-oidc-python`,
  `module-auth-oidc-vue`, `module-dev-auth-bypass`,
  `module-runtime-config-spa`.

## Tasks

### Task 1 — Backend auth (model: opus)

- `auth/oidc.py`: discovery + cached `PyJWKClient`; validate RS256,
  `exp`, `nbf`, `aud`, `iss`. No custom crypto.
- `auth/dev.py`: HS256 dev tokens, selected by unverified `alg` header
  only when `ADRIANO_DEV_SHARED_SECRET` is set; same `aud`/`iss`
  enforcement; dev router `/auth/dev/token` mounted only when
  `ADRIANO_DEV_AUTH_ENABLED` (loud warning log). `adriano mint-dev-token
  --sub --name --email --roles` CLI; `task mint-dev-token`.
- `auth/deps.py`: `Principal(issuer, subject, display, email, roles)`
  from claims (roles via `ADRIANO_OIDC_ROLES_CLAIM` dotted path);
  `require_permission("read"|"operate")` using `auth/rbac.py` and the
  `rbac` config block. Dev and real tokens share the same downstream
  path.
- Protect all existing `/api/v1` routes with `read`; add
  `POST /api/v1/sources/poll` and `/sources/{id}/poll` with `operate`
  (run via the polling service in a background task; return 202 with
  the run id; status visible in `/sources`). `GET /api/v1/me`.
- Tests: 401 without token, 403 without permission, operate vs read,
  HS256 accepted only with secret, rejected without it, unknown alg,
  wrong aud/iss, RS256 never routed to dev validator (use a locally
  generated RSA key + mocked JWKS), dev router 404 when disabled.

### Task 2 — Frontend auth (model: sonnet)

- `src/auth/oidc.ts` (`UserManager`, in-memory store), callback route,
  TokenProvider wiring, re-auth loop guard with blocking error dialog,
  `useMe` composable from `/api/v1/me`, sign-in/sign-out in app bar.
- Runtime config keys for OIDC (authority, client id, redirect URIs)
  in `config.ts` + `public/config.js` stub; dev-auth gate is a
  build-time literal (`import.meta.env.DEV && VITE_DEV_AUTH === 'true'`)
  and never in runtime config. Dev login dialog (pick sub/name/roles)
  calling `/auth/dev/token`.
- `SourcesView`: "Poll now" (all / per source) shown only with
  `operate`; otherwise an explanation of who can poll. Success and
  failure snackbars; refresh status after 202.
- Tests: re-auth guard, token provider, permission-aware rendering.
  Add `scripts/check-no-dev-auth.sh` (grep `dist/` for dev-login
  markers) and call it from `task build`.

## Acceptance criteria touched

7 (operator part), 26, 3 (poll status feedback).

## Verification (coordinator)

```
task lint && task test && task build
```

Playwright: unauthenticated view shows sign-in; dev login as reader ->
browse works, no "Poll now"; as operator -> poll succeeds and status
updates.

## Definition of done

Green checks; no route reachable without auth except `/healthz` and the
gated dev router.
