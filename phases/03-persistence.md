# Phase 03 — Persistence

## Goal

A DB-neutral storage port with a PostgreSQL implementation, the initial
Alembic migration (constraints, FTS, append-only trigger), and
integration tests against the ephemeral test database.

## Prerequisites

- Phases 01–02 `done`.

## Context to read

- `phases/DECISIONS.md`: "Persistence", "Approval semantics".
- `SPEC.md`: "Architecture and persistence", the persistence paragraph
  of "Independent approval and sign-off workflow".
- quartermaster `module-database-postgresql` (migrations, model
  conventions, query conventions).

## Tasks

### Task 1 — Port, models, migration, store, tests (model: opus)

- `app/storage/port.py`: `CatalogStore` Protocol plus value types
  (dataclasses, not ORM objects) used by services. Operations needed
  through phase 07 (keep it minimal, no speculative methods):
  - registrations: sync from config, get/list, update poll status;
  - revisions: put-if-absent, get by digest;
  - records: upsert published by `(source_id, project, path)`, upsert
    candidate by `(source_id, project, record_key, ref)` with
    create-only variant (conflict signal), get by id, list change
    tokens for a registration/project, delete published rows by ids,
    list identity siblings, list relationship summaries;
  - search: `search(query, filters, page, page_size)` returning items +
    total; filters `source_id`, `project`, `kind`, and a precomputed
    `needs_approval` predicate pushed into SQL (see note below);
  - decisions: append event (raises a domain `DecisionExistsError` on
    unique violation), list events for an identity;
  - intake runs: start/finish, find by delivery id;
  - `lock_registration(source_id)` context for advisory locking.
- `app/storage/postgres/models.py` + `store.py` with SQLAlchemy 2
  `select()` style, sessions per unit of work, bound parameters only.
- Migration `0001_initial` (hand-reviewed): all tables from
  DECISIONS.md; explicit index names; partial unique indexes; generated
  or trigger-maintained weighted `tsvector` (`simple` config so code
  identifiers and UUIDs are searchable; add an `english` component for
  body text if cheap); GIN index; append-only trigger on
  `decision_event` that raises on UPDATE/DELETE; `COMMENT ON` for
  non-obvious columns; working `downgrade()`.
- Needs-approval in SQL: implement the six-state rule as a SQL
  expression/lateral join over `decision_event` so the filter is
  paginated correctly, and keep it consistent with
  `domain/approval.evaluate` (add a test that compares both on a fixture
  set). Policy status is passed in as a parameter.
- Tests `backend/tests/storage/` using `ADRIANO_TEST_DATABASE_URL`;
  fixture runs `alembic upgrade head` once per session and truncates
  between tests. Cover: upserts, partial unique constraints, candidate
  create conflict, decision uniqueness, **UPDATE/DELETE on
  decision_event fails**, FTS finds title/body/UUID, filters, pagination
  bounds, advisory lock helper, needs-approval SQL vs domain parity,
  persistence across a new engine (restart simulation).

## Acceptance criteria touched

12 (constraint level), 16 (persistence across restart), 22.

## Verification (coordinator)

```
task db:reset
task migrate
task lint
task test
```

Also: `alembic downgrade base && alembic upgrade head` on the dev DB.

## Definition of done

Green checks; no `create_all` outside tests; services can be written
against `storage/port.py` only.
