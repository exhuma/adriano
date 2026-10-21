Authentication and access
=========================

Adriano has no user accounts of its own.
People sign in at your OIDC identity provider; Adriano trusts the
access token the provider issues and takes the user's roles from it.
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
     participant UI as Adriano web UI
     participant IdP as OIDC provider
     participant API as Adriano API

     User->>UI: opens Adriano, clicks Sign in
     UI->>IdP: redirect to sign-in
     User->>IdP: signs in
     IdP->>UI: redirect back to /auth/callback
     UI->>IdP: exchange code for tokens
     IdP-->>UI: access token (audience, roles)
     UI->>API: request with access token
     API->>IdP: fetch signing keys (first use only)
     API->>API: check signature, expiry,<br/>issuer and audience
     API->>API: map roles to permissions<br/>(catalog file)
     API-->>UI: data, or 401 / 403

The API never takes part in the sign-in itself.
It only checks each request's token.
It contacts the identity provider the first time it needs the
provider's signing keys, not at start-up, so an unreachable provider
never stops Adriano.
While the provider is unreachable, requests answer HTTP 503
(``auth_unavailable``).

Sessions are kept in browser memory only:
reloading the page or opening a new tab asks the user to sign in
again (usually without a password prompt, while the provider session
lasts).

Identity provider contract
--------------------------

Register one **public client** for the web UI
(authorization code flow with PKCE, no client secret) and configure:

Redirect URI
   ``https://<your Adriano address>/auth/callback``
   (or :envvar:`ADRIANO_OIDC_REDIRECT_URI`).
Post-logout redirect URI
   ``https://<your Adriano address>/``
   (or :envvar:`ADRIANO_OIDC_POST_LOGOUT_REDIRECT_URI`).
Web origin
   Your Adriano address, if the provider restricts browser origins.
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
Endpoints
   The provider's token and key endpoints must be on the same origin
   (scheme, host and port) as :envvar:`ADRIANO_OIDC_AUTHORITY`;
   the browser blocks requests to any other origin.

Then set in ``.env``:

.. code-block:: sh

   ADRIANO_OIDC_AUTHORITY=https://idp.example.com/realms/adr
   ADRIANO_OIDC_CLIENT_ID=adriano-web
   ADRIANO_OIDC_AUDIENCE=adr_viewer
   ADRIANO_OIDC_ROLES_CLAIM=realm_access.roles

All OIDC settings are described in :doc:`configuration`.

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

   To find a reviewer's ``issuer|subject``, decode one of their
   access tokens and read the ``iss`` and ``sub`` claims.

Push tokens for CI
------------------

Push tokens are shared secrets, one set per source registration.
A push token:

- lets a CI job submit candidates for that one registration only;
- grants no read access and works on no other request;
- is never accepted for sign-in, and sign-in tokens are never
  accepted for pushes.

See :doc:`ci-push` to create, hand out and rotate them.

What the API answers
--------------------

``401`` with ``not_authenticated``
   The request carried no token.
``401`` with ``invalid_token`` or ``token_expired``
   The token is wrong for this deployment: bad signature, wrong
   issuer or audience, or expired.
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
#. The development token endpoint does not exist:

   .. code-block:: sh

      curl -s -o /dev/null -w '%{http_code}\n' \
        -X POST https://adriano.example.com/auth/dev/token

   The answer must be ``404``.
#. The backend start-up log contains neither ``DEV AUTH ENABLED``
   nor ``dev HS256 tokens are accepted``:

   .. code-block:: sh

      docker compose logs backend | grep -i 'dev'

#. The sign-in page offers no "Dev sign-in" button.
   The production web image never contains it, whatever the
   settings; if you see one, you are not looking at a production
   build.

To turn it off, remove both variables from ``.env`` (and from the
shell environment and the backend environment file), then recreate
the backend with ``docker compose up -d backend``.
