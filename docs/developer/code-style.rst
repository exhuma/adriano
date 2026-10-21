Code style
==========

Linters enforce most of the conventions; ``task lint`` runs them all.
Fix findings instead of suppressing them.

Line length
-----------

Lines are at most 80 columns in every file type: Python, TypeScript,
reStructuredText and configuration.
Ruff enforces it for Python.
In prose, start each sentence on a new line, and break long sentences
at clause boundaries, so that diffs stay small.

Python
------

Ruff is configured in ``backend/pyproject.toml``:

- Rule sets: ``E``, ``F``, ``I`` (import order), ``D`` (docstrings),
  ``C90``, ``B`` and ``UP``.
- Line length 80 and target version Python 3.14.
- McCabe complexity at most 10 per function.
  When a function gets too complex, split it instead of raising the
  limit.
- Docstring convention ``pep257``.
  Multi-line docstrings may start the summary on the opening line or
  on the next one; follow the surrounding code.

Other conventions:

- Annotate every function fully and avoid bare ``Any``.
  Do not use ``from __future__ import annotations``.
- Imports go at the top of the module.
- The layering is routers, services, storage, with calls going
  downward only; the domain package has no I/O.
  See :doc:`api/index` for the packages.

Docstrings
^^^^^^^^^^

Every public module, class and function has a Sphinx-style docstring:
a one-line summary in the imperative mood, then ``:param name:`` and
``:returns:`` fields where applicable, and ``:raises:`` for expected
errors.
The docstrings are the reference documentation; the pages in
:doc:`api/index` are generated from them and narrative pages link to
them instead of repeating them.
Docstrings are parsed as reStructuredText, so the documentation build
fails on invalid markup, for example a list that is not followed by a
blank line.

TypeScript and Vue
------------------

ESLint runs with the recommended Vue and TypeScript presets and
``--max-warnings 0``.
Document exported functions, composables and modules with a short
comment on what they are for; generated files are excluded from
linting.
Colours and custom CSS follow the rules in :doc:`frontend`.

Commits
-------

Commits follow
`Conventional Commits <https://www.conventionalcommits.org/>`_:
``type(scope): subject``, with an imperative subject and a body that
explains why.
Typical types are ``feat``, ``fix``, ``docs``, ``refactor``, ``test``,
``build``, ``ci`` and ``chore``; the scope names the area, for example ``frontend``,
``domain``, ``storage``, ``auth``, ``backend`` or ``developer``.
Keep commits atomic: one logical change per commit, with the tests
still green, and do not mix refactoring with behaviour changes.
Never commit secrets; ``.env`` and ``.env.demo`` are gitignored.
