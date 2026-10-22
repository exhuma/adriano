0022: Backend-for-Frontend session with a confidential OIDC client
==================================================================

:Status: Accepted
:Date: 2026-10-22

Context
-------

ADR :doc:`0010-oidc-resource-server` made the SPA a public OIDC client
that kept its tokens in memory.
Two problems followed (issue #21):

* Every page reload signed the user out, because nothing restored the
  tokens at start-up.
* The silent renewal that was meant to keep a session alive did not
  work, so a session ended when the access token expired.

RFC 10017 (BCP 212, OAuth 2.0 for Browser-Based Applications)
recommends a Backend-for-Frontend (BFF) for business applications:
the backend is the OAuth client, holds the tokens, and the browser
holds only a session cookie.
Adriano already has a backend that serves the SPA from the same origin
(:doc:`0020-single-image`), so the BFF costs no new component.

Decision
--------

The backend is a **confidential** OIDC client and the only party that
talks to the identity provider.

* Sign-in is Authorization Code with PKCE (S256), ``state`` and
  ``nonce``, with client authentication at the token endpoint.
  The redirect URI is ``<origin>/auth/callback`` and the post-logout
  URI is ``<origin>/``, both derived from the request's scheme and
  ``Host`` header.
  There is no setting for either.
* Sessions are **server-side** rows in PostgreSQL (``auth_session``;
  the pending sign-ins are ``auth_login`` rows).
  Claims and IdP tokens are encrypted with a Fernet key
  (``ADRIANO_SESSION_KEY``).
  A session has an idle expiry and an absolute expiry
  (``ADRIANO_SESSION_IDLE_MINUTES``, ``ADRIANO_SESSION_MAX_HOURS``);
  ``adriano poll`` purges the expired rows.
* The browser holds one cookie,
  ``__Host-adriano-session``: ``Secure; HttpOnly; SameSite=Strict;
  Path=/``, no ``Domain``, no ``Max-Age``.
  Its value is an opaque random identifier.
  A short-lived ``__Host-adriano-login`` cookie (``SameSite=Lax``,
  ten minutes) binds a pending sign-in to the browser that started it.
  The callback answers a landing page that loads
  ``/auth/landing.js``, which navigates to the target, because a
  ``SameSite=Strict`` cookie is not sent on a redirect chain that
  started at the identity provider.
* Cookie-authenticated requests with an unsafe method,
  ``/auth/logout`` and ``/auth/dev/login`` need the header
  ``X-Adriano-CSRF: 1``, and a present ``Origin`` header must equal the
  request's own origin.
  Otherwise the answer is 403 ``csrf_failed``.
  CI push requests carry no cookie and are exempt.
* ``/api/v1`` user routes authenticate **only** with the session
  cookie.
  An ``Authorization: Bearer`` header on them is ignored.
* The access token is refreshed inline, when a request finds it about
  to expire.
  The refresh runs single-flight under a row lock and stores the
  rotated refresh token.
  ``invalid_grant`` deletes the session (401 ``session_expired``);
  an unreachable provider answers 503.
* Sign-out is RP-initiated: ``POST /auth/logout`` deletes the session,
  revokes the refresh token when the provider offers a revocation
  endpoint, and returns the provider's end-session URL for the browser
  to follow.
* The dev login creates a **dev session** (claims only, no tokens)
  through ``POST /auth/dev/login``.
  HS256 dev tokens, ``POST /auth/dev/token`` and
  ``adriano mint-dev-token`` are removed.
  The guards of :doc:`0011-dev-auth-bypass` stay.
* This is a clean cut.
  There is no compatibility mode: bearer-token user authentication,
  ``oidc-client-ts`` and the SPA callback route are deleted.

Alternatives considered
-----------------------

In-memory tokens and a top-level ``prompt=none`` redirect on reload
   Restores the session without new server state.
   Rejected: every reload costs a full redirect round trip, and the
   tokens still live in JavaScript.
``sessionStorage`` with refresh tokens
   Survives a reload.
   Rejected: any XSS can read the tokens, and long-lived refresh
   tokens in the browser are the lowest tier of RFC 10017.
A token-mediating backend
   The backend runs the code flow but hands the access token to the
   SPA.
   Rejected: the access token is still in JavaScript.
An encrypted client-side cookie session
   Needs no table.
   Rejected: the cookie would hit the 4 KB limit with real tokens, and
   a session could not be revoked.

Consequences
------------

* This is a **breaking deploy change**.
  Operators must add ``ADRIANO_SESSION_KEY`` and
  ``ADRIANO_OIDC_CLIENT_SECRET``, and change the identity provider
  client to confidential.
  ``ADRIANO_OIDC_REDIRECT_URI`` and
  ``ADRIANO_OIDC_POST_LOGOUT_REDIRECT_URI`` are gone.
  Every user signs in once after the upgrade.
* The backend is no longer stateless: sessions live in PostgreSQL
  (migration 0004).
  Replicas share them through the database.
* The public origin must reach the backend intact.
  The proxy must pass ``Host`` unchanged and
  ``ADRIANO_FORWARDED_ALLOW_IPS`` must trust it so that
  ``X-Forwarded-Proto`` is honoured.
  ``X-Forwarded-Host`` is ignored on purpose.
  Production needs HTTPS because of the ``__Host-`` cookie prefix.
* The content security policy no longer names the identity provider
  (``connect-src 'self'``, ``frame-src 'none'``), and the provider no
  longer needs web origins or CORS for Adriano.
* CI push tokens are unchanged; their future is issue #22.
