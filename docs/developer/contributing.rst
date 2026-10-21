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
