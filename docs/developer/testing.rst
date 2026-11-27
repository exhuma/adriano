Testing
=======

Run everything with ``task test`` and ``task lint``.
Both are run by the same commands on a developer machine and in CI.

Backend
-------

The backend uses pytest with ``pytest-asyncio`` (auto mode) and
Hypothesis.
Tests live in ``backend/tests`` and mirror the layers of the
application:

``tests/domain``
   Pure unit tests of parsing, hashing, validation and approval rules.
   No database, no I/O.

``tests/sources``
   The filesystem and GitLab source adapters.

``tests/services``
   Polling, ingest, search and the other service-layer behaviour.

``tests/storage``
   Integration tests of the PostgreSQL store.

``tests/routers``
   HTTP tests through FastAPI's ``TestClient``, including permissions
   and the approval workflow.

``tests/auth``
   Claim mapping, the OIDC validator, cookies, CSRF and the command
   line.

``tests/routers/oidc``
   The sign-in, refresh and sign-out flows against a fake provider.

Test doubles
^^^^^^^^^^^^

Nothing in the suite talks to the network or to a real provider.

``tests/fakes.py``
   ``FakeSource``, an in-memory implementation of the source port.
   It records every call and scripts failures and incomplete listings.

``tests/gitlab_fake.py``
   ``FakeGitLab``, a GitLab REST API v4 served through
   ``httpx.MockTransport`` with realistic pagination and scripted
   failures.

``tests/auth_helpers.py``
   A throwaway dev secret and session key, ``FakeIdp`` (a local RSA
   key pair posing as an OIDC provider), and the client helpers.
   ``https_client(app)`` builds a test client for an ``https://``
   base URL, so ``Secure`` cookies are kept, and adds the
   ``X-Adriano-CSRF`` header to unsafe requests.
   ``sign_in(client, sub=..., roles=...)`` signs it in through
   ``POST /auth/dev/login`` and returns the session cookie.

Test database
^^^^^^^^^^^^^

Storage, service and router tests use a real PostgreSQL database.
Start it with:

.. code-block:: sh

   task db:up

The container listens on host port 55432 and contains two databases:
``adriano`` for development and ``adriano_test`` for the tests.
The tests read ``ADRIANO_TEST_DATABASE_URL`` and never touch the
development database.
The storage fixtures build the schema once per session by running
the real Alembic migrations (including ``downgrade base``) and
truncate all tables before each test.

Running tests
^^^^^^^^^^^^^

.. code-block:: sh

   cd backend
   uv run pytest                           # everything
   uv run pytest tests/domain              # one directory
   uv run pytest tests/domain/test_hashing.py::test_name
   uv run pytest -k "approval and not parity"

Test docstrings begin with "Ensure ..." and state the behaviour
under test.

Frontend
--------

The frontend uses Vitest with jsdom and Vue Test Utils.
Tests live in ``frontend/tests`` and mirror ``src/``: ``api``,
``auth``, ``components``, ``composables``, ``plugins``, ``utils`` and
``views``.
``tests/setup.ts`` supplies the browser APIs Vuetify needs and jsdom
lacks.

.. code-block:: sh

   cd frontend
   npm ci
   npm run test                      # whole suite, once
   npx vitest run tests/utils/diff.test.ts
   npx vitest run -t "pattern"       # by test name

``task test`` unsets ``VITE_DEV_AUTH`` so that a developer's ``.env``
cannot change the outcome.

Some tests guard conventions rather than behaviour:

- ``style-blocks.test.ts`` fails when a ``<style>`` block contains a
  hard-coded colour or a rule without a justification comment (see
  :ref:`developer/frontend:Vuetify first`).
- ``plugins/vuetify.test.ts`` checks that every theme text and
  background pair reaches a contrast ratio of at least 4.5:1.
- ``typography-scale.test.ts`` protects the type scale.

Lint and type checks
--------------------

``task lint`` runs, in this order:

``ruff check``
   Rule sets E, F, I, D (pydocstyle, ``pep257`` convention), C90
   (complexity at most 10), B and UP, configured in
   ``backend/pyproject.toml``.

``ruff format --check``
   The formatter, with a line length of 80.

``npm run lint``
   ESLint with the Vue and TypeScript presets and no warnings allowed.

``npm run typecheck``
   ``vue-tsc --build``.

Python type checking is configured for Pyright in
``pyrightconfig.json`` at the repository root (it uses
``backend/.venv``) but is not part of ``task lint``.
Editors that use Pylance pick it up automatically.
