Docker Compose
==============

This page takes you from nothing to a running, healthy Adriano with
Docker Compose, against your own catalog file and identity provider.
Read :doc:`index` first; it explains what you deploy and how to
register the identity provider client.
Read this page top to bottom; every step is required unless marked
optional.

Prerequisites
-------------

- Docker Engine with Docker Compose v2.24 or newer.
  Older Compose versions cannot read the optional environment file
  this stack uses.
- The things listed in :doc:`index`: an identity provider client, a
  record source and a TLS-terminating ingress or load balancer.

Obtaining the stack
-------------------

Download ``docker-compose.yml`` and ``deploy/compose.defaults.env``
from the source archive of the release you deploy, and keep the
relative paths: put ``compose.defaults.env`` in a ``deploy/`` folder
next to ``docker-compose.yml``.

The stack has two services:

``db``
   PostgreSQL 18 with a named volume (``adriano-db-data``).
   Remove it, and the ``depends_on`` entry of ``adriano``, if you
   use your own PostgreSQL (see `Using your own PostgreSQL`_).
``adriano``
   The Adriano image.
   It is the only service published on the host (port 8180 by
   default).

Pin the image to one release in ``.env`` (next section) and pull it:

.. code-block:: sh

   docker compose pull adriano

Configuration
-------------

You provide two files next to ``docker-compose.yml``:

``.env``
   Environment settings: database password, OIDC settings, and the
   secrets that the catalog file names (source access tokens and push tokens).
   Every setting is described in :doc:`../configuration`.
   Keep this file out of version control; it holds secrets.
``catalog.yaml``
   Which sources to index, the approval policy and the role
   permissions.
   See :doc:`../catalog-file`.

A minimal production ``.env``:

.. code-block:: sh

   # The release to run: a full version, never a channel
   ADRIANO_IMAGE_TAG=2026.10.1

   # Database (the bundled db service)
   ADRIANO_DB_PASSWORD=<long random password>
   ADRIANO_DATABASE_URL=postgresql://adriano:<same password>@db:5432/adriano

   # Your catalog file on the Docker host
   ADRIANO_CATALOG_FILE_HOST=./catalog.yaml

   # OIDC: Adriano is a confidential client of your provider
   ADRIANO_OIDC_AUTHORITY=https://idp.example.com/realms/adr
   ADRIANO_OIDC_CLIENT_ID=adriano
   ADRIANO_OIDC_CLIENT_SECRET=<client secret>
   # Encrypts the sessions at rest. Generate once with:
   # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ADRIANO_SESSION_KEY=<Fernet key>
   ADRIANO_OIDC_AUDIENCE=adr_viewer
   ADRIANO_OIDC_ROLES_CLAIM=realm_access.roles

   # Secrets that catalog.yaml refers to by name
   # only needed for a gitlab source
   ADRIANO_GITLAB_TOKEN_PLATFORM=<GitLab access token>
   ADRIANO_PUSH_TOKEN_PLATFORM=<long random token>

   # Never set the dev-only sign-in settings here:
   # ADRIANO_DEV_AUTH_ENABLED, ADRIANO_DEV_SHARED_SECRET

.. warning::

   :envvar:`ADRIANO_CATALOG_FILE_HOST` defaults to the bundled demo
   catalog.
   Always set it to your own file, or Adriano indexes the sample
   records.
   The ``./samples`` mount in ``docker-compose.yml`` only serves the
   demo catalog; remove it once you use your own.

The bundled database address uses the default credentials.
When you change :envvar:`ADRIANO_DB_PASSWORD`, change the password in
:envvar:`ADRIANO_DATABASE_URL` as well.

Validate the catalog file before the first start
(the database does not need to be running):

.. code-block:: sh

   docker compose run --rm --no-deps adriano adriano check-config

Fix every line marked ``error`` before you continue.

Bring-up
--------

#. Start the stack:

   .. code-block:: sh

      docker compose up -d

   Compose starts ``db``, waits until it is healthy, then starts
   ``adriano``.
   Adriano applies pending database migrations before it serves
   (set :envvar:`ADRIANO_MIGRATE_ON_START` to ``false`` to turn this
   off and run ``adriano migrate`` yourself).
#. Point your ingress or load balancer at the published port, with
   TLS.
   Pass the ``Host`` header through unchanged and forward the
   ``X-Forwarded-For`` and ``X-Forwarded-Proto`` headers.
   Sign-in builds its redirect address, and the CSRF check its
   expected origin, from the scheme and ``Host`` the browser used.
   Adriano trusts them only from the addresses in
   :envvar:`ADRIANO_FORWARDED_ALLOW_IPS`: set it to your proxy's
   address, or to ``*`` if only the proxy can reach the published
   port.
#. Run the first poll, so the catalog has content:

   .. code-block:: sh

      docker compose exec adriano adriano poll

   Each registration prints one line with its status and counts.
   See :doc:`../polling` for what ``partial`` and ``failed`` mean.
#. Schedule polls, as described in the next section.
#. If CI should push draft records, hand out the push tokens
   (:doc:`../ci-push`).

Scheduling polls
----------------

Compose has no scheduler.
Run ``adriano poll`` from cron or a systemd timer on the Docker host,
for example every 15 minutes:

.. code-block:: text

   */15 * * * * docker compose -f /opt/adriano/docker-compose.yml exec -T adriano adriano poll >> /var/log/adriano-poll.log 2>&1

``-T`` is needed because cron has no terminal.
Alert on a non-zero exit code; :doc:`../polling` lists them.

Verification
------------

#. The service is healthy:

   .. code-block:: sh

      docker compose ps -a

   ``adriano`` and ``db`` show ``healthy``.
#. The health endpoint answers:

   .. code-block:: sh

      curl -fsS http://localhost:8180/healthz

   A healthy production deployment answers:

   .. code-block:: json

      {"status": "ok", "database": "ok", "config": "ok",
       "policy": "configured", "registrations": "synced",
       "rbac": "configured", "auth": "oidc", "version": "2026.10.1"}

   ``version`` is the release you pinned.
   ``auth`` must be ``oidc``.
   Any value containing ``dev`` means the development sign-in
   bypass is active: stop and fix it (see :doc:`../authentication`).
   Every field is explained in :doc:`../health-and-logging`.
#. Open the web UI through your ingress and sign in with a user that
   has the ``read`` permission.
   The sign-in page must not offer a "Dev sign-in" button.
#. Sign in as an operator and open the Sources page.
   Every registration should show the status OK.

Trusting an internal certificate authority
------------------------------------------

If your identity provider or GitLab uses a certificate from an
internal certificate authority, give Adriano the authority's
certificate.
Adriano then trusts it in addition to the public authorities.
Put the PEM file (for example ``internal-ca.pem``) in a folder on the
Docker host, and mount that folder read-only in a
``docker-compose.override.yml`` next to ``docker-compose.yml``:

.. code-block:: yaml

   services:
     adriano:
       volumes:
         - ./ca:/etc/adriano-ca:ro

Then point :envvar:`ADRIANO_EXTRA_CA_CERTS` at the mounted folder in
``.env``:

.. code-block:: sh

   ADRIANO_EXTRA_CA_CERTS=/etc/adriano-ca

Adriano reads the ``*.pem`` and ``*.crt`` files of the folder.
Check that it loads them; the log lists the subject of every added
certificate:

.. code-block:: sh

   docker compose run --rm --no-deps adriano adriano check-config

A wrong path or a file without a certificate stops Adriano at start,
and the message names the file.
Do not turn off verification with :envvar:`ADRIANO_TLS_VERIFY` in
production.

Upgrade and rollback
--------------------

An upgrade may change the database schema, and a schema change cannot
be undone by going back to the old image.
Back up the database first (:doc:`../backup-restore`).
Then:

#. Set ``ADRIANO_IMAGE_TAG`` in ``.env`` to the new version.
#. Validate your catalog file against the new release
   (``docker compose run --rm --no-deps adriano adriano check-config``).
#. Pull and recreate:

   .. code-block:: sh

      docker compose pull adriano
      docker compose up -d

   The new container applies the migrations before it serves.
   Plan a short maintenance window: the old release may not work
   against the new schema.
#. Verify as above.

To roll back, set the previous version and run ``docker compose up
-d``.
That works only while the release you left did not change the
schema.
If it did, restore the backup taken before the upgrade
(:doc:`../backup-restore`) and then start the previous version.
:doc:`../upgrades` has the details.

Using your own PostgreSQL
-------------------------

To use a managed PostgreSQL (version 18 is what Adriano is tested
with):

#. Set :envvar:`ADRIANO_DATABASE_URL` in ``.env`` to its address.
   Your value wins over the bundled default.
#. Remove the ``db`` service and the ``depends_on`` entry of
   ``adriano`` from ``docker-compose.yml``.

For production, create the two database users described in
:ref:`operator/backup-restore:Database roles and tamper resistance`.
Run the migrations with the owner and the application with the
application user: start once with
:envvar:`ADRIANO_DATABASE_URL` set to the owner's address, then switch
it to the application user's address, or set
:envvar:`ADRIANO_MIGRATE_ON_START` to ``false`` and run the
migrations with the owner before each upgrade:

.. code-block:: sh

   docker compose run --rm --no-deps \
     -e ADRIANO_DATABASE_URL=<owner address> adriano adriano migrate
