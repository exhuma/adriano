Command-line reference
======================

The Adriano image contains the ``adriano`` command.
Its default command is ``adriano serve``; the other commands are
administrative tasks you run as one-off commands.

.. code-block:: sh

   # Compose, in the running container
   docker compose exec adriano adriano <command>
   # Compose, in a new container
   docker compose run --rm --no-deps adriano adriano <command>
   # Kubernetes
   kubectl exec deployment/adriano -- adriano <command>

It uses the same environment and catalog file as the running
container.

``adriano serve``
-----------------

.. program:: adriano serve

The container command: applies pending database migrations (unless
:envvar:`ADRIANO_MIGRATE_ON_START` is ``false``), then serves the web
UI and the API on port 8000 with :envvar:`ADRIANO_WORKERS` worker
processes.
If the migration fails, the command exits with code ``2`` and serves
nothing.
You rarely run it by hand.

``adriano migrate``
-------------------

.. program:: adriano migrate

Applies pending database migrations under a database lock and exits.
Running it several times, or at the same time, is safe.
Use it as an init container or before a rollout when
:envvar:`ADRIANO_MIGRATE_ON_START` is ``false`` (:doc:`upgrades`).

Exit codes: ``0`` on success, ``2`` when the database is unreachable
or a migration fails.

``adriano check-config``
------------------------

.. program:: adriano check-config

Validates the catalog file and the sign-in settings.
Needs no database, so it works before the first start.

.. code-block:: text

   Configuration file: /app/catalog.yaml (ok)
   Registrations (2):
     gitlab-platform [gitlab] enabled (intake: poll, push; ref: @project-default)
     central [filesystem] DISABLED: root: Field required
   Approval policy: configured (global v1, required=true)
   RBAC roles: adr-admin, adr-reader
   Problems (3):
     warning: sources[0] (gitlab-platform): push token env var ADRIANO_PUSH_TOKEN_PLATFORM is not set
     warning: sources[0] (gitlab-platform): push intake is enabled but no push token is set; every push is refused
     error: sources[1] (central): disabled: root: Field required
   Authentication: oidc

Each problem is an ``error`` (something is disabled or blocked) or a
``warning`` (works, but probably not as intended, such as an unset
push token).

Exit codes: ``0`` without errors (warnings allowed), ``1`` with at
least one error.
Run it after every change to the catalog file and before every
upgrade.

``adriano poll``
----------------

.. program:: adriano poll

Stores the registrations from the catalog file, then polls every
enabled registration that has ``poll`` in its ``intake``,
one after another, in the order of the catalog file.

.. option:: --source <id>

   Poll only this registration.

Output: one line per registration with its status and counts
(projects, documents, fetched, unchanged, created, updated, deleted,
failed), followed by its problems:

.. code-block:: text

   gitlab-platform: ok (projects 12, documents 87, fetched 3, unchanged 84, created 1, updated 2, deleted 0, failed 0)

Exit codes:

``0``
   Every polled registration is ``ok``.
``1``
   At least one is ``partial``, ``failed`` or ``disabled``.
``2``
   Unknown ``--source``, or the database is unreachable.

See :doc:`polling` for scheduling and what the statuses mean.

Development-only commands
-------------------------

These commands exist for development and benchmarking.
Do not use them on a production deployment.

``adriano mint-dev-token``
   Prints a development sign-in token for any user and roles.
   It works only when :envvar:`ADRIANO_DEV_SHARED_SECRET` is set,
   which it must never be in production;
   on a correctly configured deployment it fails with exit code 2.
``adriano seed-synthetic``
   Fills the database with generated test records for benchmarking.
   It refuses databases whose name does not look like a development
   or test database.
