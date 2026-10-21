Configuration reference
=======================

Adriano is configured in two places:

- **Environment settings**, listed on this page.
- **The catalog file**, which lists the sources, the approval policy
  and the role permissions (:doc:`catalog-file`).

Settings take effect when the services start.
Change a value, then recreate the affected service
(``docker compose up -d``).

Where to put settings
---------------------

With the bundled Docker Compose stack, put every setting in the
``.env`` file next to ``docker-compose.yml``.

.. important::

   The stack itself fixes some backend values, and those win over
   anything else:

   - The database address is always built from
     :envvar:`ADRIANO_DB_USER`, :envvar:`ADRIANO_DB_PASSWORD` and
     :envvar:`ADRIANO_DB_NAME`.
     To use another database, see
     :ref:`operator/install:Using your own PostgreSQL`.
   - :envvar:`ADRIANO_CONFIG_FILE` always points at the file named by
     :envvar:`ADRIANO_CATALOG_FILE_HOST`.
   - The OIDC, development sign-in, staleness and worker settings
     are read from ``.env`` (or the shell that runs
     ``docker compose``) only.
     If you point :envvar:`ADRIANO_BACKEND_ENV_FILE` at another file,
     use that file only for the secrets the catalog file names.

Values shown as ``<...>`` in the examples are placeholders.
Never copy them literally, and never commit real secrets.

Backend settings
----------------

.. envvar:: ADRIANO_DATABASE_URL

   :Required: yes; the backend refuses to start without it
   :Default: none
   :Example: ``postgresql://adriano_app:<password>@pg.example.com:5432/adriano``

   Address of the PostgreSQL database, as a plain ``postgresql://``
   URL.
   With the bundled stack this value is built for you and cannot be
   set in ``.env``.
   If the database cannot be reached, the backend still starts,
   but ``/healthz`` answers HTTP 503 and every page fails to load.

.. envvar:: ADRIANO_CONFIG_FILE

   :Required: yes, when you run the backend outside the bundled stack
   :Default: ``catalog.yaml`` in the working directory
   :Example: ``/etc/adriano/catalog.yaml``

   Path of the catalog file inside the backend container.
   The bundled stack sets it for you; use
   :envvar:`ADRIANO_CATALOG_FILE_HOST` instead.
   A missing or unreadable file does not stop the backend:
   no source is indexed, decisions are refused, and ``/healthz``
   reports ``config: missing`` or ``config: invalid``.

.. envvar:: ADRIANO_OIDC_AUTHORITY

   :Required: yes, for production sign-in
   :Default: none (OIDC sign-in is off)
   :Example: ``https://idp.example.com/realms/adr``

   Base URL of your OIDC identity provider; Adriano appends
   ``/.well-known/openid-configuration`` to find it.
   Setting it turns on OIDC sign-in, for the API and for the web UI.
   It must be a plain ``http(s)://host[:port][/path]`` URL
   without query, fragment, user name or password;
   otherwise the web container refuses to start.
   If the provider is unreachable, the application keeps running,
   and requests that need a signed-in user answer HTTP 503 until it is
   reachable again.
   Without this setting (and without the development secret), nobody
   can sign in and ``/healthz`` reports ``auth: unconfigured``.

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
   When true without the secret, the backend logs an error and the
   endpoint stays off.
   See :doc:`authentication`.

.. envvar:: ADRIANO_DEV_SHARED_SECRET

   :Required: no; **must be unset in production**
   :Default: none

   Development only.
   When set, the API also accepts tokens signed with this secret,
   so anyone who knows it can act as any user, including any
   reviewer.
   The backend logs a warning at start-up and ``/healthz`` reports
   ``auth: dev`` or ``auth: oidc+dev``.
   An empty value counts as unset.

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

.. envvar:: ADRIANO_WORKERS

   :Required: no
   :Default: ``4``
   :Example: ``8``

   Number of worker processes in each backend container.
   Raise it for more concurrent users; each worker holds its own
   database connections, so check your database connection limit.

.. envvar:: SSL_CERT_FILE

   :Required: no; only for an internal certificate authority
   :Default: none (a standard set of public authorities is trusted)
   :Example: ``/etc/adriano/ca-bundle.pem``

   Path inside the backend container of a PEM file with the
   certificate authorities to trust for GitLab and the identity
   provider.
   It *replaces* the standard set, so include the public authorities
   too if you still need them.
   Mount the file read-only and put this variable in the backend
   environment file (:envvar:`ADRIANO_BACKEND_ENV_FILE`).
   Certificate checks cannot be turned off.

Bundled stack settings
----------------------

These settings belong to the bundled ``docker-compose.yml``.
They have no meaning when you run the images another way.

.. envvar:: ADRIANO_CATALOG_FILE_HOST

   :Required: yes, for any real deployment
   :Default: ``./catalog.demo.yaml`` (the demo catalog)
   :Example: ``./catalog.yaml``

   Path of your catalog file on the Docker host.
   It is mounted read-only into the backend.
   If you leave the default, Adriano indexes the bundled sample
   records instead of yours.

.. envvar:: ADRIANO_BACKEND_ENV_FILE

   :Required: no
   :Default: ``.env``
   :Example: ``secrets.env``

   File on the Docker host whose variables are passed into the
   backend container.
   Put every secret that the catalog file names there (see
   :ref:`catalog-secrets`).
   A missing file is not an error; the secrets are then simply unset
   and the affected sources are disabled.

.. envvar:: ADRIANO_DB_USER

   :Required: no
   :Default: ``adriano``

   User name of the bundled ``db`` service.
   Set it before the first start: the database is created with it,
   and changing it later does not rename the existing user.

.. envvar:: ADRIANO_DB_PASSWORD

   :Required: yes, for any real deployment
   :Default: ``adriano``
   :Example: ``<long random password>``

   Password of the bundled ``db`` service.
   The default is only acceptable for a local demo.
   Set it before the first start: changing it later does not change
   the password stored in the existing database volume.

.. envvar:: ADRIANO_DB_NAME

   :Required: no
   :Default: ``adriano``

   Database name of the bundled ``db`` service.
   Set it before the first start.

.. envvar:: ADRIANO_FRONTEND_PORT

   :Required: no
   :Default: ``8180``
   :Example: ``8443``

   Host port on which the web UI is published.
   Point your ingress or load balancer at it.

Web UI settings
---------------

These settings configure the sign-in in the browser.
In the bundled stack, set the ``ADRIANO_`` names.
When you run the web image without Compose, set the container name
shown with each entry instead;
:envvar:`ADRIANO_OIDC_AUTHORITY` is then ``OIDC_AUTHORITY``.

OIDC sign-in in the web UI is offered only when both
:envvar:`ADRIANO_OIDC_AUTHORITY` and :envvar:`ADRIANO_OIDC_CLIENT_ID`
are set.

.. envvar:: ADRIANO_OIDC_CLIENT_ID

   :Required: yes, for production sign-in
   :Default: none
   :Container name: ``OIDC_CLIENT_ID``
   :Example: ``adriano-web``

   Client ID of the web UI at your identity provider.
   Register it as a public client using the authorization code flow
   with PKCE.
   Without it the sign-in page offers no way to sign in.

.. envvar:: ADRIANO_OIDC_REDIRECT_URI

   :Required: no
   :Default: ``<web UI address>/auth/callback``
   :Container name: ``OIDC_REDIRECT_URI``
   :Example: ``https://adriano.example.com/auth/callback``

   Where the identity provider sends the browser back after sign-in.
   Register exactly this address as a redirect URI of the client.
   Override it only if the public address differs from the address
   the browser sees.

.. envvar:: ADRIANO_OIDC_POST_LOGOUT_REDIRECT_URI

   :Required: no
   :Default: the web UI address
   :Container name: ``OIDC_POST_LOGOUT_REDIRECT_URI``
   :Example: ``https://adriano.example.com/``

   Where the identity provider sends the browser after sign-out.
   Register it as an allowed post-logout redirect URI.

.. envvar:: ADRIANO_OIDC_SCOPE

   :Required: no
   :Default: ``openid profile email``
   :Container name: ``OIDC_SCOPE``
   :Example: ``openid profile email offline_access``

   Scopes requested at sign-in.
   Add ``offline_access`` if your provider should issue refresh
   tokens for background session renewal.

.. envvar:: ADRIANO_FRONTEND_API_BASE_URL

   :Required: no; leave it empty
   :Default: empty (the API is reached on the same address as the UI)
   :Container name: ``API_BASE_URL``

   Address the browser uses for API requests.
   Leave it empty.
   The web UI's security policy only allows requests to its own
   address and to the identity provider, and the API does not accept
   requests from other web addresses, so any other value breaks the
   UI.

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

- Define each named variable in the backend's environment
  (:envvar:`ADRIANO_BACKEND_ENV_FILE` in the bundled stack).
  Adding a source never needs a change to ``docker-compose.yml``.
- They are read once at start-up.
  After changing or rotating one, recreate the backend
  (``docker compose up -d backend``; a plain restart keeps the old
  values).
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
``VITE_DEV_AUTH`` and other ``VITE_`` settings
   Used only by developers running the web UI from source.
   No setting can turn on the development sign-in in the web image.
