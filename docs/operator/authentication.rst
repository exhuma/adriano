Authentication and access
=========================

Adriano has no user accounts of its own.
People sign in at your OIDC identity provider.
Adriano itself is the OIDC client: it signs the user in, keeps the
provider's tokens on the server, and gives the browser only a session
cookie.
The user's roles come from the access token.
CI jobs use separate *push tokens* that can only submit candidates.

.. danger::

   **The development sign-in must be off in production.**
   :envvar:`ADRIANO_DEV_SHARED_SECRET` and
   :envvar:`ADRIANO_DEV_AUTH_ENABLED` exist for local development.
   With the secret set, anyone who knows it can act as any user,
   including any reviewer, and approve decisions in their name.
   Leave both unset in every shared or production environment, and
   verify it after each deployment
   (:ref:`verify-dev-auth-off`).

How sign-in works
-----------------

.. mermaid::

   sequenceDiagram
     actor User
     participant UI as Browser
     participant API as Adriano
     participant IdP as OIDC provider

     User->>UI: opens Adriano, clicks Sign in
     UI->>API: GET /auth/login
     API-->>UI: redirect to the provider
     User->>IdP: signs in
     IdP->>UI: redirect to /auth/callback
     UI->>API: GET /auth/callback
     API->>IdP: exchange code (client secret)
     IdP-->>API: ID, access and refresh tokens
     API->>API: validate tokens,<br/>store encrypted session
     API-->>UI: session cookie
     UI->>API: requests with the cookie
     API->>API: map roles to permissions<br/>(catalog file)
     API-->>UI: data, or 401 / 403

The browser never sees a token.
It holds one cookie, ``__Host-adriano-session``, that is only sent to
Adriano's own address (``Secure``, ``HttpOnly``, ``SameSite=Strict``).
The tokens stay in the database, encrypted with
:envvar:`ADRIANO_SESSION_KEY`.
Adriano contacts the provider when a user signs in, to renew an
expiring access token, and when a user signs out.
It reads the provider's discovery document the first time it needs it,
not at start-up, so an unreachable provider never stops Adriano.
While the provider is unreachable, requests that need it answer
HTTP 503 (``auth_unavailable``).

Session lifetime
----------------

A reload or a new tab keeps the user signed in.
A session ends when one of these happens:

* The user is inactive for :envvar:`ADRIANO_SESSION_IDLE_MINUTES`
  (default 8 hours).
* :envvar:`ADRIANO_SESSION_MAX_HOURS` (default 24 hours) passed since
  sign-in, however active the user is.
* The provider refuses to renew the access token, for example because
  the user was disabled or the provider session ended.
* The user signs out.
  Adriano deletes the session, revokes the refresh token and also ends
  the user's session at the provider.

In every case the user's next request answers 401, and the web UI
sends them to sign in again.
A deleted session cannot be revived; so removing the rows of
``auth_session`` signs everyone out.
Changing :envvar:`ADRIANO_SESSION_KEY` has the same effect.
Expired sessions are purged by the poll job (:doc:`polling`).
Sessions live in PostgreSQL, so every replica sees them
(:doc:`scaling`).

Identity provider contract
--------------------------

Register one **confidential client** for Adriano
(authorization code flow with PKCE, client authentication on with
a client secret) and configure:

Redirect URI
   ``https://<your Adriano address>/auth/callback``.
Post-logout redirect URI
   ``https://<your Adriano address>/``.
Refresh tokens
   Enable the ``offline_access`` scope (it is part of the default
   :envvar:`ADRIANO_OIDC_SCOPE`).
   The provider should rotate refresh tokens and bound their
   lifetime; Adriano stores the newest one.
Access token audience
   Must contain :envvar:`ADRIANO_OIDC_AUDIENCE`
   (default ``adr_viewer``).
   Many providers need an explicit audience mapper for this.
Access token roles
   A list of role names at the path named by
   :envvar:`ADRIANO_OIDC_ROLES_CLAIM` (default ``roles``;
   ``realm_access.roles`` for Keycloak realm roles).
Signing algorithm
   RS256. Tokens signed any other way are refused.
Web origins
   Not needed.
   The browser never calls the provider from JavaScript, and
   Adriano's content security policy no longer names it.

Adriano builds both URIs from the address the browser used: the
request's scheme and ``Host`` header.
Behind a TLS-terminating proxy, the proxy must pass ``Host`` through
unchanged and :envvar:`ADRIANO_FORWARDED_ALLOW_IPS` must trust it, or
the redirect URI will not match the registered one
(:doc:`troubleshooting`).
Production needs HTTPS; the cookie is refused over plain HTTP, except
on ``http://localhost`` for development.

Keycloak
^^^^^^^^

#. Create a client with **Client authentication** on and the
   **Standard flow** enabled.
#. Set the valid redirect URI and the valid post-logout redirect URI
   as above.
#. Under **Credentials**, copy the client secret into
   :envvar:`ADRIANO_OIDC_CLIENT_SECRET`.
#. In the realm settings (**Tokens**), turn on **Revoke Refresh
   Token**, so that refresh tokens rotate.
#. In the realm settings (**Sessions**), set the **SSO Session Idle**
   and **SSO Session Max** to values at least as long as you want
   Adriano sessions to last; Adriano never outlives them.
#. Add the audience mapper and the roles claim as described above.

Then set (in ``.env`` with Compose, in the ConfigMap and the Secret
on Kubernetes):

.. code-block:: sh

   ADRIANO_OIDC_AUTHORITY=https://idp.example.com/realms/adr
   ADRIANO_OIDC_CLIENT_ID=adriano
   ADRIANO_OIDC_CLIENT_SECRET=<client secret>
   ADRIANO_SESSION_KEY=<Fernet key>
   ADRIANO_OIDC_AUDIENCE=adr_viewer
   ADRIANO_OIDC_ROLES_CLAIM=realm_access.roles

Generate the session key once and keep it secret:

.. code-block:: sh

   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

All settings are described in :doc:`configuration`.

Who may do what
---------------

Three separate grants control access:

``read`` permission
   Browse and search.
   Comes from the ``rbac`` section of the catalog file.
``operate`` permission
   Start polls and see source problems in detail.
   Also from ``rbac``.
Reviewer
   Approve or reject records.
   Comes from ``approval_policy.reviewers`` in the catalog file,
   by individual user or by role.

None of them implies another.
A role that ``rbac`` does not list grants nothing.
See :doc:`catalog-file` for the syntax.

.. tip::

   To find a reviewer's ``issuer|subject``, read the ``iss`` and
   ``sub`` claims of one of their access tokens at your provider
   (Adriano never shows tokens).

Push tokens for CI
------------------

Push tokens are shared secrets, one set per source registration.
A push token:

- lets a CI job submit candidates for that one registration only;
- grants no read access and works on no other request;
- is never accepted for sign-in, and a session is never accepted
  for pushes.

See :doc:`ci-push` to create, hand out and rotate them.

What the API answers
--------------------

``401`` with ``not_authenticated``
   The request carried no session cookie.
``401`` with ``session_expired``
   The session is unknown or ended (idle or maximum lifetime,
   sign-out, or the provider refused renewal).
   The user signs in again.
``401`` with ``invalid_token``
   The provider's token failed validation (signature, issuer or
   audience).
``403`` with ``csrf_failed``
   A state-changing request lacked the ``X-Adriano-CSRF`` header or
   came from another origin (:doc:`troubleshooting`).
``403`` with ``permission_required``
   The user is signed in, but none of their roles grants the needed
   permission in ``rbac``.
``503`` with ``auth_unconfigured``
   No sign-in method is configured; nobody can sign in.
``503`` with ``auth_unavailable``
   The identity provider (or its signing keys) cannot be reached.

The health endpoint and the API reference page (``/api/docs``) need
no sign-in; they contain no records and no secrets.

.. _verify-dev-auth-off:

Verifying the development sign-in is off
----------------------------------------

Run these checks after every deployment and after every change to
``.env``.

#. The health endpoint reports OIDC only:

   .. code-block:: sh

      curl -fsS https://adriano.example.com/healthz

   ``auth`` must be ``oidc``.
   ``dev`` or ``oidc+dev`` means :envvar:`ADRIANO_DEV_SHARED_SECRET`
   is set.
#. The development login endpoint does not exist:

   .. code-block:: sh

      curl -s -o /dev/null -w '%{http_code}\n' \
        -X POST https://adriano.example.com/auth/dev/login

   The answer must be ``404``.
#. The start-up log contains neither ``DEV AUTH ENABLED``
   nor ``dev auth is active``:

   .. code-block:: sh

      docker compose logs adriano | grep -i 'dev'

#. The sign-in page offers no "Dev sign-in" button.
   The production web image never contains it, whatever the
   settings; if you see one, you are not looking at a production
   build.

To turn it off, remove both variables from ``.env`` (and from the
shell environment and the environment file), then recreate
the container with ``docker compose up -d adriano`` (Kubernetes:
``kubectl rollout restart deployment/adriano``).
