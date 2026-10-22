Security
========

This page is the developer-level threat model:
who can do what, how each path is authenticated,
and which controls a change must not weaken.
Deployment hardening (TLS, secrets in the platform, database roles,
backups) is an operator task, see :doc:`/operator/index`.
The rules that tests pin are listed in :doc:`invariants`.

Assets and actors
-----------------

What needs protecting
   The approval history (``decision_event``) and the content snapshots
   it refers to; the catalog content itself (internal decisions);
   GitLab tokens and CI push tokens.

Who acts
   Readers and reviewers (browser, session cookie),
   operators (session with ``operate``),
   CI pipelines (push token),
   and anyone on the network who can reach the frontend.

Trust boundaries
   The browser, CI and the sources are untrusted input.
   The OIDC provider is trusted to authenticate people.
   PostgreSQL is trusted storage, but not tamper-evident
   (see `Audit integrity`_).

Authentication paths
--------------------

.. mermaid::

   flowchart TD
     req(["request"])
     pub{"/healthz, /openapi.json<br/>or /api/docs?"}
     intake{"/api/v1/candidates?"}
     push["push-token check<br/>app.auth.push"]
     cookie{"session cookie?"}
     csrf{"unsafe method:<br/>CSRF header, Origin"}
     sess["server-side session<br/>refresh if expiring"]
     deny["401"]
     forbid["403 csrf_failed"]
     principal["Principal<br/>issuer, subject, email, roles"]
     perm["require_permission<br/>read or operate"]

     req --> pub
     pub -- "yes" --> pubok["public, no record data"]
     pub -- "no" --> intake
     intake -- "yes" --> push
     intake -- "no" --> cookie
     cookie -- "none, unknown or ended" --> deny
     cookie -- "yes" --> csrf
     csrf -- "fails" --> forbid
     csrf -- "ok" --> sess
     sess -- "valid" --> principal
     sess -- "refused by IdP" --> deny
     principal --> perm

Sessions (people)
   The backend is a confidential OIDC client
   (:doc:`decisions/0022-backend-for-frontend-session`).
   :mod:`app.services.oidc_login` runs the code flow with PKCE, state
   and nonce.
   It validates the ID token (``iss``, ``aud``, ``nonce``, ``exp``) and
   the access token with :mod:`app.auth.oidc` (signature, ``exp``,
   ``nbf``, ``aud`` and ``iss`` with PyJWT; no custom crypto).
   :mod:`app.services.auth_sessions` stores the result as a session
   row.
   An unacceptable session is 401; an unreachable IdP or no configured
   mechanism is 503.
   Token values are never logged or echoed.

Token storage
   Claims and the IdP tokens are encrypted with a Fernet key
   (``ADRIANO_SESSION_KEY``) in the ``auth_session`` table.
   The browser never receives a token.
   A session has an idle and an absolute expiry; ``adriano poll``
   purges expired rows.
   Changing the key makes every stored session unreadable, which ends
   them.

Cookies
   ``__Host-adriano-session``: an opaque random identifier with
   ``Secure; HttpOnly; SameSite=Strict; Path=/``, no ``Domain`` and no
   ``Max-Age``.
   Server-side expiry is authoritative.
   ``__Host-adriano-login`` (``SameSite=Lax``, ten minutes) binds a
   pending sign-in to its browser; its ``auth_login`` row is single
   use.
   The callback answers a landing page whose script
   (``/auth/landing.js``, so no inline script) navigates onwards,
   because a ``SameSite=Strict`` cookie is not sent on the redirect
   chain that started at the IdP.

CSRF
   Cookie-authenticated requests with an unsafe method, and
   ``/auth/logout`` and ``/auth/dev/login``, need the header
   ``X-Adriano-CSRF: 1``; a present ``Origin`` header must equal the
   request's own origin (scheme and ``Host``).
   Failures are 403 ``csrf_failed``.
   ``SameSite=Strict`` is the first line of defence; the header and
   origin check add a second (:mod:`app.auth.csrf`).
   ``X-Forwarded-Host`` is deliberately ignored.

Refresh
   An access token that is about to expire is refreshed inline, once
   at a time per session (row lock), and the rotated refresh token is
   stored.
   ``invalid_grant`` deletes the session.

Logout
   ``POST /auth/logout`` deletes the session, revokes the refresh
   token at the IdP when it offers a revocation endpoint (best
   effort) and returns the IdP's end-session URL (with
   ``id_token_hint``) for RP-initiated logout.

Claims to principal
   :py:obj:`app.auth.deps.principal_from_claims` maps ``iss`` and ``sub`` to
   the identity, ``name`` or ``preferred_username`` to the display name,
   ``email`` (dropped when ``email_verified`` is false) and the roles
   at ``ADRIANO_OIDC_ROLES_CLAIM``.
   No user is stored; the claims live in the session.

Push tokens (CI)
   Per-registration shared secrets, resolved at startup from the env
   var names in ``push_tokens_env``.
   :mod:`app.auth.push` hashes both sides with SHA-256 and compares with
   ``hmac.compare_digest``, checking every configured token without an
   early exit, so neither content nor length leaks through timing.
   A push token authorizes writing candidates to its own registration
   and nothing else; intake refuses sessions, and read routes refuse
   push tokens.
   Push requests carry no cookie and are exempt from the CSRF check.
   Intake authenticates *before* it parses the body, so an
   unauthenticated caller learns nothing about registrations or the
   expected shape.

Frontend
   The SPA holds no tokens and talks only to its own origin.
   A page reload restores the session from the cookie.

Authorization
-------------

Permissions
   ``read`` and ``operate`` come from the ``rbac`` section of
   ``catalog.yaml``, mapping IdP roles to permissions.
   A missing or invalid section grants nothing (deny by default).
   Catalog routes need ``read``; poll triggers need ``operate``;
   ``/api/v1/me`` needs only a signed-in session.

Reviewing
   Not a permission.
   Eligibility comes only from the approval policy
   (``issuer|subject`` or role); ``read`` never implies it.
   See :doc:`domain/approval` for the decision checks, including
   self-approval and its limits.

Scope of reads
   The diff endpoint answers only for digests related to the record,
   so it cannot be used to read arbitrary snapshots.

Untrusted content
-----------------

ADR files come from sources and CI and are untrusted.

Parsing
   YAML is loaded with ``yaml.safe_load``.
   Parsing never raises for content, so a hostile file cannot stop a
   poll or affect other records.

Rendering
   Markdown is rendered with markdown-it-py and sanitized with nh3 at
   ingest (:py:obj:`app.services.ingest.render_markdown`):
   scripts, event handlers and unsafe URLs are removed and links get
   ``rel="noopener noreferrer"``.
   Only the stored, sanitized HTML is rendered with ``v-html``
   (``RecordDecisionCard.vue``, ``ErratumTextBlocks.vue``).
   A change to rendering must keep sanitization at ingest.

Size limits
   Push intake refuses bodies over 8 MiB and document content over
   1 MiB (413).
   Reviewer comments are limited to 2,000 characters.

Browser hardening
-----------------

The backend adds these headers to every response
(``SecurityHeadersMiddleware`` in ``backend/app/web.py``):

``Content-Security-Policy``
   ``default-src 'self'``, ``script-src 'self'``,
   ``style-src 'self' 'unsafe-inline'`` (Vuetify sets theme variables
   in inline ``style`` attributes),
   ``connect-src 'self'``, ``frame-src 'none'``,
   ``frame-ancestors 'none'``, ``base-uri 'none'``,
   ``form-action 'self'``.

``X-Content-Type-Options``
   ``nosniff``.

``Referrer-Policy``
   ``strict-origin-when-cross-origin``.

The browser never contacts the identity provider from JavaScript, so
the policy does not name it.

The development bypass
----------------------

Dev login lets a developer sign in as any identity,
so it is guarded at three independent points
(:doc:`decisions/0011-dev-auth-bypass`):

Backend sessions
   Dev sessions (claims only, no IdP tokens) are accepted only while
   dev auth is active, i.e. ``ADRIANO_DEV_SHARED_SECRET`` is set and
   the flag is true.
   They are refused as soon as it is switched off.
   The secret has no default and dev auth needs
   ``ADRIANO_SESSION_KEY``.

Backend router
   ``/auth/dev/login`` and ``/auth/dev/roles`` are imported and mounted
   only when ``ADRIANO_DEV_AUTH_ENABLED`` is true and the secret is set,
   with a loud warning in the log.
   Otherwise they are a plain 404.
   The login route needs the CSRF header like any other.

Frontend build
   The dev-login UI is reachable only when the build-time literal
   ``import.meta.env.DEV && VITE_DEV_AUTH === "true"`` is true,
   which is never the case in a production build, and is never part
   of runtime configuration.
   ``frontend/scripts/check-no-dev-auth.sh`` runs after every
   ``npm run build`` and fails if dev-login markers
   (``/auth/dev/login``, ``/auth/dev/roles``, ``DevLoginDialog``)
   appear in ``dist/``.

With a real issuer configured, a dev session can impersonate any
``issuer|subject``, including a reviewer.
That is why the secret must never be set in production.

Secrets
-------

* ``catalog.yaml`` holds env var **names** (``token_env``,
  ``push_tokens_env``), never values.
  Values are resolved once at startup by :mod:`app.composition` and held
  as ``pydantic.SecretStr``.
* Secrets never appear in log lines, error messages, stored
  ``config`` JSON or ``intake_run`` rows;
  secret-looking keys in ``config`` are redacted defensively.
* The GitLab token is sent only in the ``PRIVATE-TOKEN`` header,
  over HTTPS with certificate verification, without following
  redirects; pagination links outside the API root are refused,
  so the token is never sent to another origin.

Audit integrity
---------------

``decision_event`` is append-only through database triggers
(see :doc:`domain/schema`).
They stop application bugs and ordinary mistakes,
not a table owner or superuser, who can disable or drop them.
Running the application as a database role that does not own the tables
and has no ``TRUNCATE`` or ``ALTER`` grant is the stronger mitigation.
Neither is cryptographic; a signed audit export is the deferred answer
(:doc:`domain/hashing`).

Known gaps
----------

* No rate limiting on push intake; every request, including refused
  ones, writes an ``intake_run`` row.
* A repeated ``delivery_id`` returns the earlier result without
  comparing the body; it is retry protection, not a content check.
* ``OIDC_AUTHORITY`` with a bracketed IPv6 host is refused at
  container start.
* The sign-in flow has not been exercised against a real provider; it
  is tested against a fake IdP (``FakeIdp``).
* Sessions are not listed or revocable per user from the UI; deleting
  rows of ``auth_session`` is the only lever.
* Roles are fixed at sign-in and when the access token is refreshed;
  a role change at the IdP applies at the next refresh or sign-in.
* Self-approval cannot be detected for polled records, which have no
  author.
