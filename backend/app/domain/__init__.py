"""
Pure domain core of the adriano catalog.

Everything in this package is free of I/O: no web framework, no database,
no HTTP client and no filesystem access. Modules:

- :mod:`app.domain.hashing` -- canonical content digest (``sha256-v1``).
- :mod:`app.domain.issues` -- validation issue value types.
- :mod:`app.domain.frontmatter` -- YAML frontmatter splitting and loading.
- :mod:`app.domain.records` -- ADR parsing, validation, title/date
  derivation and record identity.
- :mod:`app.domain.relationships` -- link resolution, inbound links,
  errata, derived display status and duplicate UUID detection.
- :mod:`app.domain.approval` -- approval policy, approval-state
  evaluation and reviewer eligibility.
"""
