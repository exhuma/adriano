Configuration reference
=======================

Adriano is configured in two places:

- **Environment settings**, listed on this page.
- **The catalog file**, which lists the sources, the approval policy
  and the role permissions (:doc:`catalog-file`).

Settings take effect when the container starts.
Change a value, then recreate the container
(``docker compose up -d``, or ``kubectl rollout restart``).

Where to put settings
---------------------

Docker Compose
   Put every setting in the ``.env`` file next to
   ``docker-compose.yml``.
   It overrides the defaults shipped in
   ``deploy/compose.defaults.env`` (the bundled database address and
   the catalog path inside the container).
   :ref:`catalog-secrets` belong in the same file.
Kubernetes
   Put non-secret settings in a ConfigMap and secrets in a Secret,
   both passed to the container as environment variables
   (:doc:`deploy/kubernetes`).
``docker run``
   Pass each setting with ``-e``.

Values shown as ``<...>`` in the examples are placeholders.
Never copy them literally, and never commit real secrets.

Application settings
--------------------

.. envvar:: ADRIANO_DATABASE_URL

   :Required: yes; Adriano refuses to start without it
   :Default: none
   :Example: ``postgresql://adriano_app:<password>@pg.example.com:5432/adriano``

   Address of the PostgreSQL database, as a plain ``postgresql://``
   URL.
   Add ``?sslmode=require`` (or stricter) for a database outside your
   own network.
   A missing or malformed value stops the container at start.
   If the database is merely unreachable, Adriano still starts,
   but ``/healthz`` answers HTTP 503 and every page fails to load.
   With the bundled Compose stack the default points at the ``db``
   service; set this variable in ``.env`` to use another database.

.. envvar:: ADRIANO_CONFIG_FILE

   :Required: yes, outside the bundled Compose stack
   :Default: ``catalog.yaml`` in the working directory
   :Example: ``/etc/adriano/catalog.yaml``

   Path of the catalog file inside the container.
   The bundled Compose stack sets it for you; use
   :envvar:`ADRIANO_CATALOG_FILE_HOST` instead.
   A missing or unreadable file does not stop Adriano:
   no source is indexed, decisions are refused, and ``/healthz``
   reports ``config: missing`` or ``config: invalid``.

.. envvar:: ADRIANO_MIGRATE_ON_START

   :Required: no
   :Default: ``true``
   :Example: ``false`` (Kubernetes, where an init container migrates)

   Whether the container applies pending database migrations before
   it starts serving.
   Containers starting at the same time are safe: one applies the
   migrations while the others wait.
   A migration can change the database in a way that cannot be undone
   (:doc:`upgrades`).
   Set it to ``false`` when you run ``adriano migrate`` yourself, for
   example as a Kubernetes init container or with a different
   database user; then a container never changes the schema on its
   own.
   If a migration fails, the container exits with code 2.

.. envvar:: ADRIANO_WORKERS

   :Required: no
   :Default: ``4``
   :Example: ``2``

   Number of worker processes in each container; at least ``1``.
   Raise it for more concurrent users.
   Each worker holds its own database connections and roughly 100 to
   150 MiB of memory, so check your database connection limit and the
   container's memory limit.

.. envvar:: ADRIANO_FORWARDED_ALLOW_IPS

   :Required: no
   :Default: ``127.0.0.1``
   :Example: ``10.0.0.5,10.0.0.6``, or ``*`` behind a Kubernetes
      ingress

   Comma-separated addresses of the proxies whose ``X-Forwarded-For``
   and ``X-Forwarded-Proto`` headers Adriano trusts.
   Behind an ingress or load balancer, set it to the proxy's address;
   otherwise Adriano sees every request as coming from the proxy and
   may build ``http://`` links.
   ``*`` trusts every peer: use it only when nothing but the proxy
   can reach the container.

.. envvar:: ADRIANO_STATIC_DIR

   :Required: no; do not change
   :Default: ``/app/static`` in the image

   Folder with the web UI.
   The image sets it.
   If you unset it, the container serves the API only, without the
   web UI.
   A folder without an ``index.html`` stops the container at start.

.. envvar:: ADRIANO_VERSION

   :Required: no; do not set
   :Default: the release version of the image (``dev`` outside a
      release)

   The version that ``/healthz`` reports.
   The image sets it; it only helps you confirm which release runs.

.. envvar:: ADRIANO_STALE_AFTER_MINUTES

   :Required: no
   :Default: ``120``
   :Example: ``45`` (when you poll every 15 minutes)

   How long after a source's last successful poll its content is
   flagged as possibly out of date (on the Sources page and on record
   pages).
   Set it to a few poll intervals.
   A source whose last poll failed or was partial, or that was never
   polled successfully, is always flagged, whatever this value.

.. envvar:: SSL_CERT_FILE

   :Required: no; only for an internal certificate authority
   :Default: none (a standard set of public authorities is trusted)
   :Example: ``/etc/adriano/ca-bundle.pem``

   Path inside the container of a PEM file with the certificate
   authorities to trust for GitLab and the identity provider.
   It *replaces* the standard set, so include the public authorities
   too if you still need them.
   Mount the file read-only.
   This is the way to trust an internal certificate authority;
   prefer it over :envvar:`ADRIANO_TLS_VERIFY`.

.. envvar:: ADRIANO_TLS_VERIFY

   :Required: no
   :Default: ``true``
   :Example: ``false`` (a non-production instance only)

   Whether Adriano verifies the server certificate when it calls the
   identity provider (discovery document and signing keys) and
   GitLab.
   ``false`` turns all certificate checks off: anyone who can
   intercept that traffic can then impersonate the identity provider
   and get any token accepted, or feed false content into the catalog.
   Use it only as a stop-gap on a test or staging instance, never in
   production; trust your certificate authority with
   :envvar:`SSL_CERT_FILE` instead.
   While it is ``false``, Adriano logs a warning at start-up and when
   it first contacts the identity provider.

Sign-in settings
----------------

One identity provider serves the API and the web UI.
Both :envvar:`ADRIANO_OIDC_AUTHORITY` and
:envvar:`ADRIANO_OIDC_CLIENT_ID` are required together:
Adriano refuses to start with only one of them.

.. envvar:: ADRIANO_OIDC_AUTHORITY

   :Required: yes, for production sign-in
   :Default: none (OIDC sign-in is off)
   :Example: ``https://idp.example.com/realms/adr``

   Base URL of your OIDC identity provider; Adriano appends
   ``/.well-known/openid-configuration`` to find it.
   Setting it turns on OIDC sign-in, for the API and for the web UI.
   It must be a plain ``http(s)://host[:port][/path]`` URL
   without query, fragment, user name or password;
   otherwise the container refuses to start.
   The web UI is allowed to contact the origin of this URL and no
   other identity provider.
   If the provider is unreachable, the application keeps running,
   and requests that need a signed-in user answer HTTP 503 until it is
   reachable again.
   Without this setting (and without the development secret), nobody
   can sign in and ``/healthz`` reports ``auth: unconfigured``.

.. envvar:: ADRIANO_OIDC_CLIENT_ID

   :Required: yes, for production sign-in
   :Default: none
   :Example: ``adriano-web``

   Client ID of the web UI at your identity provider.
   Register it as a public client using the authorization code flow
   with PKCE (:doc:`deploy/index`).
   Must be set together with :envvar:`ADRIANO_OIDC_AUTHORITY`.

.. envvar:: ADRIANO_OIDC_SCOPE

   :Required: no
   :Default: ``openid profile email``
   :Example: ``openid profile email offline_access``

   Scopes requested at sign-in.
   Add ``offline_access`` if your provider should issue refresh
   tokens for background session renewal.

.. envvar:: ADRIANO_OIDC_REDIRECT_URI

   :Required: no
   :Default: ``<web UI address>/auth/callback``
   :Example: ``https://adriano.example.com/auth/callback``

   Where the identity provider sends the browser back after sign-in.
   Register exactly this address as a redirect URI of the client.
   Override it only if the public address differs from the address
   the browser sees.

.. envvar:: ADRIANO_OIDC_POST_LOGOUT_REDIRECT_URI

   :Required: no
   :Default: the web UI address
   :Example: ``https://adriano.example.com/``

   Where the identity provider sends the browser after sign-out.
   Register it as an allowed post-logout redirect URI.

.. envvar:: ADRIANO_OIDC_ISSUER

   :Required: no
   :Default: the issuer announced by the provider
   :Example: ``https://idp.example.com/realms/adr``

   Issuer that access tokens must name.
   Leave it empty unless your provider announces a different issuer
   than the one it writes into its tokens.
   An empty value counts as unset.

.. envvar:: ADRIANO_OIDC_AUDIENCE

   :Required: no
   :Default: ``adr_viewer``
   :Example: ``adriano``

   Audience that access tokens must carry.
   Configure your identity provider to put this value into the
   audience of the access tokens it issues to the web UI client;
   tokens without it are refused (HTTP 401).

.. envvar:: ADRIANO_OIDC_ROLES_CLAIM

   :Required: no
   :Default: ``roles``
   :Example: ``realm_access.roles`` (Keycloak)

   Where in the access token the user's role names are, as a dotted
   path to a list of strings.
   The catalog file maps these role names to permissions.
   If the path is missing from a token, that user has no roles and
   therefore no permissions.

.. envvar:: ADRIANO_DEV_AUTH_ENABLED

   :Required: no; **must be unset or false in production**
   :Default: ``false``

   Development only.
   When true *and* :envvar:`ADRIANO_DEV_SHARED_SECRET` is set,
   the API offers an endpoint that issues a sign-in token for any
   user and any roles, without a password.
   When true without the secret, Adriano logs an error and the
   endpoint stays off.
   See :doc:`authentication`.

.. envvar:: ADRIANO_DEV_SHARED_SECRET

   :Required: no; **must be unset in production**
   :Default: none

   Development only.
   When set, the API also accepts tokens signed with this secret,
   so anyone who knows it can act as any user, including any
   reviewer.
   Adriano logs a warning at start-up and ``/healthz`` reports
   ``auth: dev`` or ``auth: oidc+dev``.
   An empty value counts as unset.

Docker Compose settings
-----------------------

These settings belong to the bundled ``docker-compose.yml``
(:doc:`deploy/docker-compose`).
They have no meaning on other platforms.

.. envvar:: ADRIANO_IMAGE_TAG

   :Required: yes, for any real deployment
   :Default: ``edge`` (the latest build of the main branch)
   :Example: ``2026.10.1``

   Tag of ``ghcr.io/exhuma/adriano`` to run.
   Use a full release version in production; a channel tag
   (``stable``, ``beta``, ``alpha``, ``rc``) or ``edge`` moves under
   you (:doc:`deploy/index`).

.. envvar:: ADRIANO_PORT

   :Required: no
   :Default: ``8180``
   :Example: ``8443``

   Host port on which Adriano is published (the container always
   listens on 8000).
   Point your ingress or load balancer at it.

.. envvar:: ADRIANO_CATALOG_FILE_HOST

   :Required: yes, for any real deployment
   :Default: ``./catalog.demo.yaml`` (the demo catalog)
   :Example: ``./catalog.yaml``

   Path of your catalog file on the Docker host.
   It is mounted read-only into the container.
   If you leave the default, Adriano indexes the bundled sample
   records instead of yours.

.. envvar:: ADRIANO_BACKEND_ENV_FILE

   :Required: no
   :Default: ``.env``
   :Example: ``secrets.env``

   File on the Docker host whose variables are passed into the
   container, on top of the shipped defaults.
   Because the stack passes no other settings, this file is the single
   source of all of them, secrets included
   (see :ref:`catalog-secrets`).
   A missing file is not an error; the settings are then simply unset.

.. envvar:: ADRIANO_DB_USER

   :Required: no
   :Default: ``adriano``

   User name of the bundled ``db`` service.
   Set it before the first start: the database is created with it,
   and changing it later does not rename the existing user.
   Update :envvar:`ADRIANO_DATABASE_URL` to match.

.. envvar:: ADRIANO_DB_PASSWORD

   :Required: yes, for any real deployment
   :Default: ``adriano``
   :Example: ``<long random password>``

   Password of the bundled ``db`` service.
   The default is only acceptable for a local demo.
   Set it before the first start: changing it later does not change
   the password stored in the existing database volume.
   Update :envvar:`ADRIANO_DATABASE_URL` to match.

.. envvar:: ADRIANO_DB_NAME

   :Required: no
   :Default: ``adriano``

   Database name of the bundled ``db`` service.
   Set it before the first start.
   Update :envvar:`ADRIANO_DATABASE_URL` to match.

.. _catalog-secrets:

Secrets named by the catalog file
---------------------------------

The catalog file never contains secret values.
It names environment variables instead,
for GitLab access tokens (``token_env``) and CI push tokens
(``push_tokens_env``).
You choose those names; by convention they start with
``ADRIANO_GITLAB_TOKEN_`` and ``ADRIANO_PUSH_TOKEN_``.

.. code-block:: sh

   ADRIANO_GITLAB_TOKEN_PLATFORM=<GitLab access token>
   ADRIANO_PUSH_TOKEN_PLATFORM=<long random token>

- Define each named variable in the container's environment
  (the ``.env`` file with Compose, the Secret on Kubernetes).
  Adding a source never needs a change to the deployment files.
- They are read once at start-up.
  After changing or rotating one, recreate the container
  (``docker compose up -d adriano``, or
  ``kubectl rollout restart deployment/adriano``; a plain Compose
  restart keeps the old values).
- A missing GitLab token disables only that source;
  a missing push token makes that source refuse every push.
  ``adriano check-config`` names the missing variable.
- Secret values are never logged or shown; messages only name the
  variable.

Generate push tokens as long random strings, for example with
``openssl rand -hex 32``.

Settings you can ignore
-----------------------

``ADRIANO_TEST_DATABASE_URL``
   Used only by the project's test suite; a deployment never reads
   it.
