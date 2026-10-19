# Phase 05 — Browse slice (read API + UI)

## Goal

Readers can search the catalog, filter by source/project and
candidate/published, open a readable detail page, and see source
freshness — all from the local index without source calls.

## Prerequisites

- Phases 01–04 `done`.

## Context to read

- `phases/DECISIONS.md`: "HTTP API", "Frontend end state".
- `SPEC.md`: "User decisions", "UI requirements", criteria 2, 4, 5,
  21, 24.
- quartermaster `module-ux-principles` (feedback, accessibility).

## Tasks

### Task 1 — Read API (model: sonnet)

- `services/{search,record_detail,record_relationships}.py` (store only) and routers:
  - `GET /api/v1/records` with `q`, `source`, `project`, `state`,
    `page`, `page_size` (max 50). Result items: id, title, source,
    project, path, ref, kind, approval state summary, issue counts,
    derived status. (`needs_approval` arrives in phase 07; do not add it
    yet.)
  - `GET /api/v1/records/{id}` detail per DECISIONS.md (approval
    fields may report the state computed from the policy; decision
    history and actions arrive in phase 07).
  - `GET /api/v1/sources` with freshness/status per registration and a
    `stale` flag (last success older than a configurable threshold
    `ADRIANO_STALE_AFTER_MINUTES`, or last status failed/partial).
  - `GET /api/v1/facets` (or fields on `/sources`) listing
    sources/projects for the filter select.
- Pydantic response models; 404 domain errors via handlers.
- Test that read routes never construct an adapter: patch
  `sources.registry` factory to raise, exercise every read route.
- Simple timing assertion is **not** required here (benchmark in 09).

### Task 2 — Browse UI (model: sonnet)

- `src/types/` interfaces for the new payloads (derive from OpenAPI;
  commit a generation script if using `openapi-typescript`).
- `useSearchQuery` composable: two-way sync of `q`, `source`, `project`,
  `state`, `page` with the URL; debounced search; "Clear filters".
- `SearchView`: search field, source/project select, all/candidate/
  published toggle, results list (compact rows: title, source/project,
  state chip, approval chip, issue indicator with count and accessible
  label), pagination, loading/empty/error+retry states.
- `RecordView`: sanitized HTML (server-sanitized; render with `v-html`
  only for that field), metadata panel (uuid, date with "inferred"
  label, kind, path, ref), validation issues list, provenance + source
  link, freshness + stale/failed banner text from DECISIONS.md,
  outbound/inbound links and errata as router links, legacy sign-off
  section titled "Legacy sign-off (unverified)", sibling revisions.
- `SourcesView`: table of registrations with status chips, last
  attempt/success, error summary and recovery hint.
- vitest for `useSearchQuery` and view-model helpers.

## Acceptance criteria touched

2, 4, 5, 14, 15 (display), 21, 23, 24.

## Verification (coordinator)

```
task lint && task test && task build
```

Seed the dev DB by polling a small filesystem tree, run both dev
servers, and walk search -> filter -> detail -> link -> sources with
Playwright (keyboard-only pass for the search page). Screenshots to
scratchpad.

## Definition of done

Green checks and a working keyboard-operable browse flow.
