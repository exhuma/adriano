Contributing
============

Workflow
--------

1. Create a short-lived branch off the main branch.
2. Make small, atomic changes.
   Follow :doc:`code-style` and add tests (:doc:`testing`).
3. Run ``task lint`` and ``task test``.
   If you touched documentation or docstrings, run ``task docs`` too.
4. Open a pull request with a clear title and description.
   Review the diff yourself first and keep the pull request to a
   single purpose.

Change the documentation together with the behaviour it describes, in
the same pull request.

Where documentation goes
------------------------

The site is organised by audience, and each page belongs to exactly
one.

:doc:`/user/index`
   Task-oriented pages for readers and reviewers.
   Short, free of jargon, and illustrated with screenshots.

:doc:`/operator/index`
   Deploying, configuring and running Adriano.
   Describe consequences (what happens, what to check) rather than
   mechanisms, and do not mention development workflow.

:doc:`index`
   Everything for engineers: architecture, decisions, how-tos and the
   generated references.
   Implementation detail belongs here.

Do not copy docstrings into narrative pages.
Document the behaviour of code in its docstring, which appears in
:doc:`api/index`, and link to it with ``:mod:``, ``:class:`` or
``:func:``.
Refer to other pages with ``:doc:`` or, for sections, with the page
path as prefix, for example ``:ref:`developer/frontend:Vuetify first```.

Building the docs locally
-------------------------

.. code-block:: sh

   task docs          # build into docs/_build/html
   task docs:serve    # build, then serve on http://localhost:8765

Both use the ``docs`` dependency group of the backend project and run
Sphinx with ``-W``, so any warning fails the build.
The build imports the backend modules for autodoc and writes the
OpenAPI document to ``docs/_generated/openapi.json`` for the HTTP
reference; neither needs a database.
``docs/_build/`` and ``docs/_generated/`` are gitignored.

Writing reStructuredText
^^^^^^^^^^^^^^^^^^^^^^^^

- Wrap lines at 80 columns with one sentence per line, or break long
  sentences at clauses.
  Long URLs, code and paths may exceed the limit.
- Use the heading hierarchy ``=`` (title, once), ``-``, ``^``.
- Do not put paragraphs in table cells; use definition lists, or
  ``.. envvar::`` for settings.
- Give code blocks a language: ``.. code-block:: sh``.

Screenshots
-----------

- Store images in ``docs/_static/screenshots/``.
  The file ``INVENTORY.rst`` there lists the curated set; it is a
  working list for authors and not a page of the site.
- Every image has meaningful ``:alt:`` text that says what the reader
  should see, not just "screenshot".
- Capture with a dev sign-in on the demo data (``task demo`` and
  ``task demo:ui``) so that no real identities or data appear.
- Prefer a crop to the relevant region.
- Keep the screenshot and the caption consistent with the text, and
  retake it when the UI changes.

Diagrams
--------

Draw diagrams as code with ``.. mermaid::``
(``sphinxcontrib-mermaid``).

- The site-wide theme in ``docs/conf.py`` uses the Okabe-Ito
  colour-blind-safe palette on a white panel.
  Do not add inline colours unless they come from that palette.
- Never encode meaning by colour alone.
  Label every edge and state, and use shapes or text to distinguish
  kinds of nodes.
- Keep each diagram small enough to read without zooming, and explain
  it in the text next to it.

Documentation CI
----------------

The workflow ``.github/workflows/docs.yml`` builds the site with the
same command as ``task docs`` on every pull request, so a warning
fails the check.
On the main branch (``master``) it also publishes the built site to
GitHub Pages.
If the check fails, reproduce it locally with ``task docs``.

Releases and images
-------------------

Continuous integration
^^^^^^^^^^^^^^^^^^^^^^

Three workflows live in ``.github/workflows``:

``testing.yml``
   The reusable test suite (``workflow_call``): ruff and pytest against
   a PostgreSQL 18 service, eslint, ``vue-tsc``, vitest and the
   production build of the frontend, and the self-tests of the release
   scripts.
   It has no event triggers of its own, so it never runs twice for the
   same event.
``image.yml``
   Owns the triggers (pull requests, pushes to ``master``, ``v*`` tags
   and manual dispatch).
   It calls ``testing.yml``, builds the image from the root
   ``Dockerfile``, smoke-tests it and, outside pull requests, pushes it
   to ``ghcr.io/exhuma/adriano``.
``docs.yml``
   Builds the documentation (see `Documentation CI`_).

What each event publishes:

.. list-table::
   :header-rows: 1
   :widths: 22 46 32

   * - Event
     - Image tags
     - ``ADRIANO_VERSION``
   * - Pull request
     - none (build and smoke test only)
     - ``pr-<number>``
   * - Push to ``master``
     - ``edge``, ``sha-<short>``
     - ``edge-<short>``
   * - Tag ``vYYYY.M.D``
     - ``YYYY.M.D``, ``stable``, ``beta``, ``alpha``
     - ``YYYY.M.D``
   * - Tag ``vYYYY.M.D-beta.N``
     - ``YYYY.M.D-beta.N``, ``beta``, ``alpha``
     - ``YYYY.M.D-beta.N``

The version is baked into the image (build argument
``ADRIANO_VERSION``) and reported by ``/healthz``.
The image is never tagged ``latest``: CalVer has no ordering to anchor
it, so operators pin a full version or follow a channel.

CalVer tags and channels
^^^^^^^^^^^^^^^^^^^^^^^^

Releases are driven by tags of the form ``vYYYY.M.D`` with an optional
pre-release suffix ``-alpha.N``, ``-beta.N`` or ``-rc.N`` (for example
``v2026.6.15`` or ``v2026.6.15-alpha.1``).
Month and day have no leading zero.
Every release publishes its immutable full version plus the moving
channels it advances.
Channels cascade by maturity:

- ``-alpha.N`` moves ``alpha``
- ``-beta.N`` moves ``beta`` and ``alpha``
- ``-rc.N`` moves ``rc``
- no suffix (stable) moves ``stable``, ``beta`` and ``alpha``

``scripts/derive_channels.sh`` implements the mapping.

Version-sync guard
^^^^^^^^^^^^^^^^^^

On a tag push, ``scripts/check_version_sync.sh`` fails the run unless
both manifests carry the tag's version, each in its own canonical form:

- ``frontend/package.json`` keeps the tag verbatim
  (``2026.6.15-alpha.1``);
- ``backend/pyproject.toml`` uses the PEP 440 form
  (``2026.6.15a1``; ``-beta.N`` becomes ``bN``, ``-rc.N`` becomes
  ``rcN``).

The guard runs first, before the tests, and prints an ``::error::``
line naming the manifest that disagrees.
Run it locally with ``scripts/check_version_sync.sh v2026.6.15``, and
the self-tests of both scripts with
``scripts/tests/test_release_scripts.sh``.

Cutting a release
^^^^^^^^^^^^^^^^^

#. Pick the version, for example ``2026.6.15`` or
   ``2026.6.15-rc.1``.
#. Set ``version`` in ``frontend/package.json`` (verbatim) and in
   ``backend/pyproject.toml`` (PEP 440 form).
#. Refresh the lock files so they record the new version:
   ``cd backend && uv lock`` and
   ``cd frontend && npm install --package-lock-only``.
#. Verify with ``scripts/check_version_sync.sh v2026.6.15``.
#. Commit (``chore(release): 2026.6.15``) and merge to ``master``.
#. Tag the merge commit and push the tag:

   .. code-block:: sh

      git tag v2026.6.15
      git push origin v2026.6.15

#. Watch the ``image`` workflow; the image and its channel tags appear
   under the repository's packages.

A tag whose manifests disagree fails before anything is built or
published; fix the manifests, delete the tag and tag again.

Smoke-testing an image locally
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

CI runs ``scripts/smoke_test_image.sh`` on every event.
With Docker, curl and python3 available you can run the same checks:

.. code-block:: sh

   docker build -t adriano:local .
   scripts/smoke_test_image.sh adriano:local

The script starts a throwaway PostgreSQL 18 container, starts the
image twice (the second start proves the migrations are idempotent),
and checks ``/healthz``, ``/config.js``, the security headers, the SPA
fallback, the API authentication and error responses, the immutable
asset cache and the non-root user.
It removes everything it started and prints the container logs when a
check fails.
Pass a second argument (``http://127.0.0.1:9000``) when port 8000 is
taken.
