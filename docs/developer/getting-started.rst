Getting started
===============

This page sets up a development environment, starts the application
with sample data and lists every ``task`` command.

Prerequisites
-------------

- `uv <https://docs.astral.sh/uv/>`_, which also installs the required
  Python version (3.14 or newer).
- `Node.js <https://nodejs.org/>`_ 20 or newer for the frontend.
- `Docker <https://www.docker.com/>`_ for the ephemeral database and
  the demo stack.
- `go-task <https://taskfile.dev/>`_ version 3, which provides the
  ``task`` command.

Dev container
^^^^^^^^^^^^^

The repository ships a dev container in ``.devcontainer/``.
It is based on the Ubuntu dev container image with Python 3.14,
Node 24 and Docker-outside-of-Docker.
Its ``init.bash`` post-create script installs ``uv`` and ``task`` if
they are missing, runs ``uv sync`` in ``backend/`` and ``npm ci`` in
``frontend/``.
It forwards the ports 8100 (backend), 5173 (frontend dev server) and
55432 (database).
Inside the container only the environment file and the catalog below
still need to be created.

Set up the environment
----------------------

.. code-block:: sh

   # Dev-only settings; both secrets must stay unset in production.
   cp .env.example .env
   openssl rand -hex 32          # use the output as the dev secret

   # A configured catalog to poll: the bundled demo catalog.
   cp catalog.demo.yaml catalog.yaml

   # Backend dependencies.
   cd backend && uv sync && cd ..

Edit ``.env`` and set:

.. code-block:: sh

   ADRIANO_DEV_AUTH_ENABLED=true
   ADRIANO_DEV_SHARED_SECRET=<output of openssl rand -hex 32>
   VITE_DEV_AUTH=true

The first two switch on the backend's dev-only HS256 token path and
the ``/auth/dev`` routes.
``VITE_DEV_AUTH`` shows the "Dev sign-in" dialog in the Vite dev
server.
Production builds never contain that dialog, whatever the variable
says (see :doc:`frontend`).
``.env.example`` documents every ``ADRIANO_`` setting; the defaults
already point at the ephemeral database on port 55432.
``catalog.yaml`` is gitignored, as is ``.env``.

Run the application
-------------------

.. code-block:: sh

   task dev

starts the ephemeral Postgres container, applies the Alembic
migrations and runs the backend on port 8100 and the Vite dev server
on port 5173.
Ctrl-C stops both servers; the database keeps running until
``task db:down``.

To run the steps separately, use one terminal each:

.. code-block:: sh

   task db:up          # ephemeral database (no-op if running)
   task migrate        # apply migrations
   task dev:backend    # backend with reload, port 8100
   task dev:frontend   # frontend, port 5173

Index the sample ADRs from ``samples/adr-root`` in another terminal:

.. code-block:: sh

   task poll

Open http://localhost:5173.
The backend answers on http://localhost:8100; with it running,
``curl -fsS localhost:8100/healthz`` reports the state of each
subsystem.

Dev sign-in
^^^^^^^^^^^

The "Dev sign-in" chip offers preset identities: Reader, Reviewer and
Operator.
The presets are derived from the roles in the loaded
``catalog.yaml``, so a preset the catalog cannot satisfy is hidden.
Roles can always be typed by hand.
The dialog uses the backend's ``POST /auth/dev/token`` and
``GET /auth/dev/roles`` routes.

To call the API from the command line, mint a token:

.. code-block:: sh

   TOKEN=$(task mint-dev-token -- --sub alice --roles admin)
   curl -H "Authorization: Bearer $TOKEN" localhost:8100/api/v1/me

The backend logs a warning at startup whenever the dev path is active.

Demo stack
----------

``task demo`` builds and starts the containerised stack (database,
migrations, backend and a production frontend build), waits for it to
become healthy, polls the sample ADRs and prints how to sign in.
It generates a gitignored ``.env.demo`` with dev auth enabled and a
push token; never reuse those values outside a throwaway local demo.

The stack publishes the frontend on http://localhost:8180.
Because that frontend is a production build, it has no dev sign-in.
Run ``task demo:ui`` in another terminal for a Vite dev server on
port 5180 with dev sign-in that proxies to the demo backend.
``task demo:poll`` re-polls the demo data and ``task demo:down``
discards the stack and its volumes.

For production deployments, see :doc:`/operator/index`.

Taskfile reference
------------------

``task --list`` prints the same list.
Pass extra arguments to the underlying command after ``--``.

``task frontend:install``
   Install the frontend dependencies with ``npm ci``.
   Skipped while ``node_modules`` matches ``package-lock.json``;
   the other frontend tasks depend on it.

``task db:up``
   Start the ephemeral dev and test Postgres container
   ``adriano-db`` on host port 55432 and create the ``adriano_test``
   database.
   A no-op if it is already running.

``task db:down``
   Stop and discard the container, including its data.

``task db:reset``
   Discard and recreate the container.

``task migrate``
   Apply the Alembic migrations to the dev database.

``task dev``
   Start the database, migrate, then run backend and frontend dev
   servers in parallel.

``task dev:backend``
   Run the FastAPI dev server with reload on port 8100.
   A relative ``ADRIANO_CONFIG_FILE`` is resolved against the
   repository root.

``task dev:frontend``
   Run the Vite dev server on port 5173.

``task poll``
   Poll all source registrations into the dev database.
   ``task poll -- --source ID`` polls one registration.

``task check-config``
   Validate ``catalog.yaml`` and print the registrations, policy and
   any problems.

``task mint-dev-token``
   Print a dev-only HS256 access token signed with the dev secret from
   ``.env``, for example
   ``task mint-dev-token -- --sub alice --roles admin``.

``task bench:seed``
   Reset and migrate the dev database (never the test database) and
   seed the deterministic synthetic benchmark corpus, by default
   20,000 records in 100 projects.
   Override with ``-- --records N --projects M``.

``task bench``
   Seed the default corpus, start a four-worker backend with a
   throwaway dev secret and run the latency benchmark
   ``backend/bench/bench.py`` at concurrency 1 and 8.
   Writes ``bench-results.json``.

``task lint``
   Run ``ruff check`` and ``ruff format --check`` in ``backend/`` and
   ESLint plus the type check in ``frontend/``.

``task test``
   Run the backend pytest suite and the frontend Vitest suite.

``task build``
   Build the production frontend bundle and verify that it contains
   no dev-login code.

``task docs``
   Build this documentation into ``docs/_build/html``.
   Warnings are errors, as in CI.

``task docs:serve``
   Build the documentation, then serve it on http://localhost:8765.

``task demo``
   Build and start the demo stack described above.

``task demo:poll``
   Poll the demo stack's sources.

``task demo:down``
   Stop and discard the demo stack.

``task demo:ui``
   Run the Vite dev server with dev sign-in against the demo backend.
