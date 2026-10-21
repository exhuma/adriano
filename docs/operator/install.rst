Installing Adriano
==================

This page takes you from nothing to a running, healthy Adriano with
Docker Compose, against your own catalog file and identity provider.
Read it top to bottom; every step is required unless marked optional.

What you deploy
---------------

Adriano runs as four services.
Two more systems are yours and are only connected to it:
your OpenID Connect (OIDC) identity provider,
and the GitLab instance or folders that hold the decision records.
CI jobs can push draft records straight to Adriano.

.. mermaid::

   flowchart LR
     browser["Browser"]
     ci["CI jobs"]
     cron["Poll schedule<br/>(cron or CronJob)"]
     idp["OIDC provider<br/>(yours)"]
     gitlab["GitLab<br/>(yours)"]

     subgraph stack["Adriano stack"]
       frontend["frontend<br/>web UI, port 8180"]
       backend["backend<br/>API"]
       migrate["migrate<br/>one-shot"]
       db[("db<br/>PostgreSQL")]
     end

     browser -- "HTTPS via your ingress" --> frontend
     browser -- "sign-in" --> idp
     ci -- "push candidates<br/>(push token)" --> frontend
     frontend -- "API requests" --> backend
     backend -- "verify tokens<br/>(signing keys)" --> idp
     backend -- "read records<br/>(access token)" --> gitlab
     cron -- "runs adriano poll" --> backend
     migrate -- "updates schema,<br/>then exits" --> db
     backend -- "reads and writes" --> db

``db``
   PostgreSQL 18 with a named volume (``adriano-db-data``).
   You may use your own managed PostgreSQL instead
   (see :ref:`operator/install:Using your own PostgreSQL`).
``migrate``
   Brings the database schema up to date, then exits.
   ``backend`` starts only after it has finished successfully.
``backend``
   The API.
   It reads the catalog file once at start-up and polls sources when
   asked.
``frontend``
   Serves the web UI and forwards API and health requests to
   ``backend``.
   It is the only service published on the host.

Prerequisites and external dependencies
---------------------------------------

Docker Engine with Docker Compose v2.24 or newer
   Older Compose versions cannot read the optional backend
   environment file this stack uses.
A TLS-terminating ingress or load balancer
   The containers speak plain HTTP.
   Put your certificate on the ingress and point it at the
   ``frontend`` port (8180 by default).
An OIDC identity provider
   Required for production sign-in.
   Register a public client for the web UI (authorization code flow
   with PKCE) and make sure access tokens carry the audience and the
   roles claim Adriano expects.
   See :doc:`authentication` for the full contract.
At least one record source
   A GitLab instance and an access token (:doc:`sources`), or a
   folder of decision records you can mount into the ``backend``
   container.
A scheduler for polling
   cron on the Docker host, or a Kubernetes ``CronJob``
   (:doc:`polling`).

Obtaining the images
--------------------

Adriano does not yet publish prebuilt container images.
Build the two images from the source archive of the release you
deploy, on the Docker host or in your own build system:

.. code-block:: sh

   docker compose build

This produces ``adriano-backend:local`` and ``adriano-frontend:local``.
If you push them to your own registry, tag them with the release
version and deploy that exact tag, never a moving tag.

Configuration
-------------

You provide two files next to ``docker-compose.yml``:

``.env``
   Environment settings: database password, OIDC settings, and the
   secrets that the catalog file names (GitLab and push tokens).
   Every setting is described in :doc:`configuration`.
   Keep this file out of version control; it holds secrets.
``catalog.yaml``
   Which sources to index, the approval policy and the role
   permissions.
   See :doc:`catalog-file`.

A minimal production ``.env``:

.. code-block:: sh

   # Database (the bundled db service)
   ADRIANO_DB_PASSWORD=<long random password>

   # Your catalog file on the Docker host
   ADRIANO_CATALOG_FILE_HOST=./catalog.yaml

   # OIDC: the API side
   ADRIANO_OIDC_AUTHORITY=https://idp.example.com/realms/adr
   ADRIANO_OIDC_AUDIENCE=adr_viewer
   ADRIANO_OIDC_ROLES_CLAIM=realm_access.roles

   # OIDC: the web UI side
   ADRIANO_OIDC_CLIENT_ID=adriano-web

   # Secrets that catalog.yaml refers to by name
   ADRIANO_GITLAB_TOKEN_PLATFORM=<GitLab access token>
   ADRIANO_PUSH_TOKEN_PLATFORM=<long random token>

   # Never set the dev-only sign-in settings here:
   # ADRIANO_DEV_AUTH_ENABLED, ADRIANO_DEV_SHARED_SECRET

.. warning::

   :envvar:`ADRIANO_CATALOG_FILE_HOST` defaults to the bundled demo
   catalog.
   Always set it to your own file, or Adriano indexes the sample
   records.

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

   Compose starts ``db``, waits until it is healthy, runs
   ``migrate``, then starts ``backend`` and finally ``frontend``.
#. Run the first poll, so the catalog has content:

   .. code-block:: sh

      docker compose exec adriano adriano poll

   Each registration prints one line with its status and counts.
   See :doc:`polling` for what ``partial`` and ``failed`` mean.
#. Set up the poll schedule (:doc:`polling`).
#. If CI should push draft records, hand out the push tokens
   (:doc:`ci-push`).

Verification
------------

#. All services are healthy:

   .. code-block:: sh

      docker compose ps -a

   ``backend`` and ``frontend`` show ``healthy``;
   ``migrate`` shows ``exited (0)``.
#. The health endpoint answers through the web container:

   .. code-block:: sh

      curl -fsS http://localhost:8180/healthz

   A healthy production deployment answers:

   .. code-block:: json

      {"status": "ok", "database": "ok", "config": "ok",
       "policy": "configured", "registrations": "synced",
       "rbac": "configured", "auth": "oidc"}

   ``auth`` must be ``oidc``.
   Any value containing ``dev`` means the development sign-in
   bypass is active: stop and fix it (see :doc:`authentication`).
   Every field is explained in :doc:`health-and-logging`.
#. Open the web UI through your ingress and sign in with a user that
   has the ``read`` permission.
   The sign-in page must not offer a "Dev sign-in" button.
#. Sign in as an operator and open the Sources page.
   Every registration should show the status OK.

Upgrade
-------

An upgrade may change the database schema, and a schema change cannot
be undone by going back to the old images.
Back up the database first, then follow :doc:`upgrades`.

Troubleshooting
---------------

See :doc:`troubleshooting`.
The most common bring-up problems:

``backend`` never starts
   ``migrate`` failed.
   Read ``docker compose logs migrate``; usually the database is
   unreachable or the credentials are wrong.
Everything is up, but nobody can sign in
   Check the ``auth`` field of ``/healthz``.
   ``unconfigured`` means no identity provider is set
   (:envvar:`ADRIANO_OIDC_AUTHORITY`).
``frontend`` restarts in a loop
   :envvar:`ADRIANO_OIDC_AUTHORITY` is not a plain
   ``http(s)://host[:port][/path]`` URL; the log says
   ``OIDC_AUTHORITY is not a valid URL``.

Using your own PostgreSQL
-------------------------

The stock ``docker-compose.yml`` always builds the database address
from :envvar:`ADRIANO_DB_USER`, :envvar:`ADRIANO_DB_PASSWORD` and
:envvar:`ADRIANO_DB_NAME`, pointing at the bundled ``db`` service.
Setting :envvar:`ADRIANO_DATABASE_URL` in ``.env`` does **not**
override that.
To use a managed PostgreSQL (version 18 is what Adriano is tested
with), add a ``docker-compose.override.yml`` next to the stack:

.. code-block:: yaml

   services:
     migrate:
       environment:
         ADRIANO_DATABASE_URL: postgresql://adriano_owner:<password>@pg.example.com:5432/adriano
     backend:
       environment:
         ADRIANO_DATABASE_URL: postgresql://adriano_app:<password>@pg.example.com:5432/adriano

Start the stack as usual.
The bundled ``db`` service still starts, because the other services
wait for it, but nothing uses it.

The two different database users in this example are recommended for
production; see
:ref:`operator/backup-restore:Database roles and tamper resistance`.

Running without Docker Compose
------------------------------

The images run on any container platform, for example Kubernetes.
Keep these points in mind:

- Run the ``migrate`` step (the backend image with the command
  ``alembic upgrade head``) once per deployment, and start the
  backend only after it succeeded.
- The backend needs every ``ADRIANO_*`` backend setting from
  :doc:`configuration` and your catalog file mounted read-only,
  with :envvar:`ADRIANO_CONFIG_FILE` pointing at it.
- The web container forwards API requests to the host name
  ``backend`` on port 8000.
  Make the backend reachable under that name, for example with a
  Kubernetes Service called ``backend``.
- The web container takes its settings under shorter names;
  :ref:`operator/configuration:Web UI settings` lists them.
- Use the backend's ``/healthz`` as readiness and liveness probe,
  and ``/config.js`` on port 8080 for the web container.

Appendix: a local demo (optional)
---------------------------------

To look at Adriano before you deploy it, a source checkout with the
``task`` command offers a throwaway demo with sample records and the
development sign-in turned on:

.. code-block:: sh

   task demo        # build, start, poll and print the URLs
   task demo:down   # stop and delete the demo stack and its data

.. danger::

   The demo uses the same Compose project name (``adriano``),
   the same database volume and the same port as a real deployment.
   Never run it on a host that runs your real deployment:
   ``task demo:down`` deletes the database volume.

The demo is never a starting point for production:
it enables the development sign-in on purpose.
