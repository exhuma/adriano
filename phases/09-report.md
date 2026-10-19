# Phase 09 — Benchmark, audit, Phase 1 report

## Goal

Measure search/browse latency, independently audit all 27 acceptance
criteria, and hand off a report. Then **stop for user review**.

## Prerequisites

- Phases 01–08 `done`.

## Context to read

- `SPEC.md`: "Phase 1 acceptance", "Phase 1 delivery and handoff".
- `phases/STATUS.md` handoff notes of all phases.

## Tasks

### Task 1 — Synthetic dataset and benchmark (model: sonnet)

- `adriano seed-synthetic --records N --projects M` pushing generated
  ADRs through `services/ingest.py` (not raw SQL), with a fixed random
  seed, realistic sizes, links, candidates, and decisions.
- `backend/bench/bench.py` (or `scripts/`): httpx against the running
  backend with a dev token; warm-up; N requests each for free-text
  search, filtered search, needs-approval filter, detail; report p50,
  p95, max. `task bench`.
- Run with 20,000 records / 100 projects (plus a 2,000 run).
- `docs/benchmark.md`: dataset, hardware/OS, DB container, worker count,
  method, results, limitations of synthetic data.

### Task 2 — Independent criteria audit (model: opus, read-only)

- Read SPEC.md criteria 1–27, inspect code, tests, docs, demo output;
  run the test suite. For each criterion: pass / fail / not measured,
  with evidence (file paths, test names, screenshots). List gaps and
  scope creep. Do not edit files; report to the coordinator.

### Task 3 — Report (model: sonnet)

- `docs/phase1-report.md`: criteria table from the audit (coordinator
  fixes or records any failures first), measured latency and
  conditions, demo summary with links to `docs/demo/`, user-authorized
  deviations (filesystem source type), known limitations, deferred
  backlog (from DECISIONS.md and anything recorded during the work).

## Verification (coordinator)

```
task lint && task test && task build && task bench
```

## Definition of done

Report committed. The coordinator presents the demo, criteria results,
latency, deferred items, and limitations to the user, then **stops**.
