Deploying Adriano
=================

Adriano ships as one container image that serves the web UI and the
API on port 8000.
This section takes you from a published release to a running,
healthy deployment, on Docker Compose or on Kubernetes.

.. toctree::
   :maxdepth: 1

   docker-compose
   kubernetes

What you deploy
---------------

You run one image, ``ghcr.io/exhuma/adriano``, and connect it to
three things you provide:

PostgreSQL
   Version 18 is what Adriano is tested with.
   Adriano needs the database address as
   :envvar:`ADRIANO_DATABASE_URL`.
   You run and back up the database yourself
   (:doc:`/operator/backup-restore`).
An OIDC identity provider
   People sign in there.
   See `Registering the client at your identity provider`_.
A catalog file
   ``catalog.yaml`` lists the sources to index, the approval policy
   and the role permissions (:doc:`/operator/catalog-file`).
   You mount it read-only into the container.

The container speaks plain HTTP.
Put a TLS-terminating ingress or load balancer in front of it.

.. mermaid::

   flowchart LR
     browser["Browser"]
     ci["CI jobs"]
     cron["Poll schedule<br/>(cron or CronJob)"]
     idp["OIDC provider<br/>(yours)"]
     gitlab["GitLab or folders<br/>(yours)"]
     db[("PostgreSQL<br/>(yours)")]

     subgraph adriano["Adriano image"]
       app["web UI and API<br/>port 8000"]
     end

     browser -- "HTTPS via your ingress" --> app
     browser -- "sign-in" --> idp
     ci -- "push candidates<br/>(push token)" --> app
     app -- "verify tokens<br/>(signing keys)" --> idp
     app -- "read records" --> gitlab
     cron -- "runs adriano poll" --> app
     app -- "reads and writes" --> db

Prerequisites
-------------

A container platform
   Docker Engine with Docker Compose v2.24 or newer, or a Kubernetes
   cluster.
PostgreSQL
   A database and a user that may create tables.
   For production, use the two-user setup from
   :ref:`operator/backup-restore:Database roles and tamper resistance`.
A TLS-terminating ingress or load balancer
   Point it at port 8000 of the container.
An OIDC identity provider
   See the next section.
At least one record source
   A GitLab instance and an access token (:doc:`/operator/sources`),
   or a folder of decision records you can mount into the container.
A scheduler for polling
   cron or a systemd timer on the Docker host, or the Kubernetes
   ``CronJob`` from the example (:doc:`/operator/polling`).

Registering the client at your identity provider
------------------------------------------------

Register one **public client** for the web UI: authorization code
flow with PKCE, no client secret.
Configure:

Redirect URI
   ``https://<your Adriano address>/auth/callback``
Post-logout redirect URI
   ``https://<your Adriano address>/``
Web origin (CORS)
   ``https://<your Adriano address>``, if the provider restricts the
   browser origins that may call its token and key endpoints.
Access token audience and roles
   The access token must carry the audience in
   :envvar:`ADRIANO_OIDC_AUDIENCE` and a list of role names at
   :envvar:`ADRIANO_OIDC_ROLES_CLAIM`.

Then set :envvar:`ADRIANO_OIDC_AUTHORITY` and
:envvar:`ADRIANO_OIDC_CLIENT_ID`.
Both are required together.
:doc:`/operator/authentication` describes the full contract.

Image tags and channels
-----------------------

Releases are published to the GitHub Container Registry as
``ghcr.io/exhuma/adriano``, tagged with a CalVer version
``YYYY.M.D`` such as ``2026.10.1`` (no leading zeros).
Pre-releases carry a suffix, for example ``2026.10.1-beta.1``.
The image is built for ``linux/amd64``.

Besides the version tags, these moving tags exist:

``stable``
   The newest final release.
``beta``
   The newest final release or beta.
``alpha``
   The newest final release, beta or alpha.
``rc``
   The newest release candidate.
``edge``
   The latest build of the main branch.
   Not a release: use it to try things out, never in production.
``sha-<7 characters>``
   A build of one commit of the main branch.

There is no ``latest`` tag.

.. important::

   In production, deploy one full version tag (for example
   ``2026.10.1``) and change it deliberately when you upgrade.
   A channel tag moves under you: a pod restart or a node change can
   silently run a newer release, whose database changes cannot be
   undone (:doc:`/operator/upgrades`).

Quick check with ``docker run``
-------------------------------

To see the image start against a database and an identity provider,
without Compose or Kubernetes:

.. code-block:: sh

   docker run --rm -p 8000:8000 \
     -e ADRIANO_DATABASE_URL=postgresql://adriano:<password>@pg.example.com:5432/adriano \
     -e ADRIANO_OIDC_AUTHORITY=https://idp.example.com/realms/adr \
     -e ADRIANO_OIDC_CLIENT_ID=adriano-web \
     -e ADRIANO_CONFIG_FILE=/etc/adriano/catalog.yaml \
     -v "$PWD/catalog.yaml:/etc/adriano/catalog.yaml:ro" \
     ghcr.io/exhuma/adriano:<version>

Then open http://localhost:8000 and check
``curl -fsS http://localhost:8000/healthz``.
For anything lasting, use one of the two guides above.

What happens at start
---------------------

The container applies pending database migrations before it starts
serving, unless you turn this off with
:envvar:`ADRIANO_MIGRATE_ON_START`.
Several containers starting at once are safe: only one applies the
migrations while the others wait.
A release may change the database schema in a way that cannot be
undone by going back to the old version; back up before every
upgrade (:doc:`/operator/upgrades`).

The container refuses to start, and logs why, when:

- :envvar:`ADRIANO_DATABASE_URL` is missing or not a ``postgresql://``
  address;
- :envvar:`ADRIANO_OIDC_AUTHORITY` is malformed, or only one of it and
  :envvar:`ADRIANO_OIDC_CLIENT_ID` is set.

:doc:`/operator/troubleshooting` lists the exact messages.

Local demo (optional)
---------------------

To look at Adriano before you deploy it, a source checkout with the
``task`` command offers a throwaway demo with sample records and the
development sign-in turned on:

.. code-block:: sh

   task demo        # build, start, poll and print the URLs
   task demo:down   # stop and delete the demo stack and its data

The demo is never a starting point for production:
it enables the development sign-in on purpose.
It runs under its own Compose project name, so ``task demo:down``
never touches a real deployment's data.
