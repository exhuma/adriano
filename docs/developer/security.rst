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
   Readers and reviewers (browser, OIDC token),
   operators (OIDC token with ``operate``),
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
     alg{"token alg header"}
     oidc["OIDC validator<br/>RS256, JWKS"]
     sec{"dev shared<br/>secret set?"}
     dev["dev validator<br/>HS256"]
     deny["401"]
     principal["Principal<br/>issuer, subject, email, roles"]
     perm["require_permission<br/>read or operate"]

     req --> pub
     pub -- "yes" --> pubok["public, no record data"]
     pub -- "no" --> intake
     intake -- "yes" --> push
     intake -- "no" --> alg
     alg -- "RS256" --> oidc
     alg -- "HS256" --> sec
     alg -- "anything else" --> deny
     sec -- "yes" --> dev
     sec -- "no" --> deny
     oidc -- "valid" --> principal
     dev -- "valid" --> principal
     principal --> perm

Bearer tokens (people)
   :py:obj:`app.auth.tokens.verify_token` picks the validator from the
   token's unverified ``alg`` header and never tries validators in
   turn, so an RS256 token can never be checked against the dev
   secret.
   :mod:`app.auth.oidc` validates signature, ``exp``, ``nbf``, ``aud`` and
   ``iss`` with PyJWT; ``exp``, ``iss``, ``aud`` and ``sub`` are
   required.
   No custom crypto.
   An unacceptable token is 401; an unreachable IdP or no configured
   mechanism is 503.
   Token values are never logged or echoed.

Claims to principal
   :py:obj:`app.auth.deps.principal_from_claims` maps ``iss`` and ``sub`` to
   the identity, ``name`` or ``preferred_username`` to the display name,
   ``email`` (dropped when ``email_verified`` is false) and the roles
   at ``ADRIANO_OIDC_ROLES_CLAIM``.
   No user is stored.

Push tokens (CI)
   Per-registration shared secrets, resolved at startup from the env
   var names in ``push_tokens_env``.
   :mod:`app.auth.push` hashes both sides with SHA-256 and compares with
   ``hmac.compare_digest``, checking every configured token without an
   early exit, so neither content nor length leaks through timing.
   A push token authorizes writing candidates to its own registration
   and nothing else; intake refuses JWTs, and read routes refuse push
   tokens.
   Intake authenticates *before* it parses the body, so an
   unauthenticated caller learns nothing about registrations or the
   expected shape.

Frontend tokens
   The SPA is a public OIDC client (Authorization Code + PKCE via
   ``oidc-client-ts``).
   Tokens live in memory only, never in ``localStorage``;
   only the short-lived PKCE state uses ``sessionStorage``.
   A page reload therefore signs the user out.

Authorization
-------------

Permissions
   ``read`` and ``operate`` come from the ``rbac`` section of
   ``catalog.yaml``, mapping IdP roles to permissions.
   A missing or invalid section grants nothing (deny by default).
   Catalog routes need ``read``; poll triggers need ``operate``;
   ``/api/v1/me`` needs only a valid token.

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

The frontend's nginx adds these headers to every response
(``frontend/security-headers.conf.template``):

``Content-Security-Policy``
   ``default-src 'self'``, ``script-src 'self'``,
   ``style-src 'self' 'unsafe-inline'`` (Vuetify sets theme variables
   in inline ``style`` attributes),
   ``connect-src`` and ``frame-src`` limited to ``'self'`` plus the
   identity provider's origin,
   ``frame-ancestors 'none'``, ``base-uri 'none'``,
   ``form-action 'self'``.

``X-Content-Type-Options``
   ``nosniff``.

``Referrer-Policy``
   ``strict-origin-when-cross-origin``.

The container entrypoint
(``docker-entrypoint.d/40-render-app-config.sh``)
validates ``OIDC_AUTHORITY`` strictly before writing its origin into
the CSP and into ``config.js``, and refuses to start on anything else,
so the setting cannot inject CSP directives.
Because nginx drops inherited ``add_header`` directives in a location
that sets its own, the snippet is included in every such location.

The development bypass
----------------------

Dev login lets a developer mint a token for any identity,
so it is guarded at three independent points
(:doc:`decisions/0011-dev-auth-bypass`):

Backend validator
   HS256 tokens are accepted only while ``ADRIANO_DEV_SHARED_SECRET``
   is set; the secret has no default.

Backend router
   ``/auth/dev/token`` and ``/auth/dev/roles`` are imported and mounted
   only when ``ADRIANO_DEV_AUTH_ENABLED`` is true and the secret is set,
   with a loud warning in the log.
   Otherwise they are a plain 404, even though the production nginx
   configuration proxies ``/auth/dev/``.

Frontend build
   The dev-login UI is reachable only when the build-time literal
   ``import.meta.env.DEV && VITE_DEV_AUTH === "true"`` is true,
   which is never the case in a production build, and is never part
   of runtime configuration.
   ``frontend/scripts/check-no-dev-auth.sh`` runs after every
   ``npm run build`` and fails if dev-login markers
   (``/auth/dev/token``, ``/auth/dev/roles``, ``DevLoginDialog``)
   appear in ``dist/``.

With a real issuer configured, a dev token is issued under that issuer
and can impersonate any ``issuer|subject``, including a reviewer.
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
* The CSP allows exactly one identity-provider origin, that of
  ``OIDC_AUTHORITY``; a provider serving endpoints from a second origin
  is blocked.
* ``OIDC_AUTHORITY`` with a bracketed IPv6 host is refused at
  container start.
* RP-initiated logout is not implemented: signing out clears the
  in-memory token but leaves the IdP session.
* The browser's Authorization Code + PKCE round trip has not been
  exercised against a real provider; backend RS256 validation is
  tested against a fake IdP's JWKS.
* Self-approval cannot be detected for polled records, which have no
  author.
