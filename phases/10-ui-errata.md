# Phase 10 — UI sidebar + erratum format

## Goal

Implement a record-page redesign (status banners at the top, metadata in a
sidebar following RFC layout) and a dedicated erratum format replacing the
`kind: erratum` + `corrects:` ADR shape.

## Prerequisites

- Phases 01–09 `done`.

## Context to read

- `phases/README.md`, `phases/DECISIONS.md`, `phases/STATUS.md`.
- `docs/schema.md`.
- The plan sections below: erratum file format, backend changes, frontend
  changes.

## Record-page layout

Follow rfc-editor.org/info pages:
- Show status prominently at the top with status banners ("This decision is
  obsoleted by …", "… was updated by …", "… has N errata").
- Make the document body the main column.
- Put all metadata in a sidebar (no tabs).

Today the page is one stack of full-width cards. The obsoleted/updated state
is a small chip plus one line, and errata are a title list near the bottom.

## Errata redesign

Today an erratum is a full ADR (`kind: erratum`, `corrects: <uuid>`), treated
like any decision everywhere: search, title, "Decision record" card. RFC errata
are small reports: type, section, original text ("says"), corrected text
("should say"), notes, and status (Reported / Verified / Rejected). Ours should
take that shape and appear on the original ADR.

### Erratum file format

Errata are separate Markdown files with their own frontmatter. The original
ADR's hash and approval stay untouched, and errata use the same poll/push
intake as ADRs.

```markdown
---
uuid: 7c1e…               # required: own identity (approval, candidates)
erratum-for: 0b0c2f4e-…   # required: UUID of the ADR being corrected
type: technical           # required: technical | editorial
section: Consequences     # optional: where in the ADR
reported-by: alice@example.com   # optional, informational only
date: 2025-05-01          # optional report date (filename date = inferred)
---
## Original text
…exact text from the ADR (optional, e.g. for pure additions)…

## Corrected text
…required…

## Notes
…optional rationale…
```

Discovery: Same path and filename rules as ADRs. The recommended location is
`doc/decisions/errata/YYYY-MM-DD-<slug>.md`. A document is an erratum because
it has `erratum-for`, not because of its path.

Body parsing: A pure parser splits the body on the H2 headings "Original text",
"Corrected text" and "Notes" (case-insensitive). Any other content is kept as
notes, with a warning.

Display title is "Erratum: <section or filename slug>". On read, the UI shows
"Erratum for <ADR title>" once the target resolves.

### Status via accept/reject

Erratum status reuses the hash-bound accept/reject workflow:
- pending = **Reported**
- accepted = **Verified**
- rejected = **Rejected**
- changed since acceptance = **Changed since verification**

Errata appear on the original ADR with a top notice and an inline section. They
are hidden from default search, and a filter can show them. Each erratum keeps
a small page of its own for review and history. The old shape (`kind: erratum`
+ `corrects:`) is replaced with no alias. Such files get a clear validation
error explaining the new format.

## Tasks

### Task 0 — Documentation and planning (model: haiku)

Write `phases/10-ui-errata.md` (this file as a resumable prompt); add a STATUS
row for phase 10; append the "Authorized post-Phase-1 change" section to
`phases/DECISIONS.md`.

### Task 1 — Domain layer (model: opus)

Domain: `domain/errata.py` parser, `erratum-for` / `type` field validation, new
issue codes, legacy-format error, `ParsedRecord.erratum`; pure unit tests.

**Issue codes:**
- `erratum_missing_corrected_text` (error)
- `bad_erratum_type` (error)
- `erratum_unknown_section_heading` (warning)
- `legacy_erratum_format` (error), raised on `kind: erratum` or `corrects`;
  the message points to `docs/schema.md`
- reuse `erratum_without_target` for missing or bad `erratum-for`
- `kind` and `corrects` are removed from `KNOWN_FIELDS`

**Changes:**
- New pure module `backend/app/domain/errata.py`: the `ErratumContent`
  dataclass (type, section, reported_by, reported_date, original, corrected,
  notes) and `parse_erratum_body()`.
- `validation.py` / `fields.py`: an `erratum-for` / `type` field parser that
  replaces `_corrects` / `_kind_field`.
- `records.py`: `ParsedRecord.erratum: ErratumContent | None`; `record_kind`
  is derived from it.
- Keep the internal `Links.corrects` (`domain/values.py`) as the link from
  erratum to target, so relationships and storage keep working. Only the
  frontmatter spelling changes.

### Task 2 — Storage layer (model: opus)

Storage: migration 0003 (`record.erratum` JSONB, `links->>'corrects'` index),
models / convert / values, ingest renders the erratum HTML, reverse lookup
incl. candidates; storage tests.

**Migration 0003:**
- Add nullable `record.erratum` JSONB with type, section, reported_by,
  reported_date, and `original_html` / `corrected_html` / `notes_html`. The
  HTML is sanitised with nh3 at ingest, using the existing
  `services/ingest.py` `render_markdown`.
- Add an expression index `ix_record_links_corrects` on `(links->>'corrects')`
  for the reverse lookup in `storage/postgres/records.py` (about lines 398-414).
- Update `models.py`, `convert.py`, and `RecordWrite`/`StoredRecord` in
  `storage/values.py`.

### Task 3 — Services and schemas (model: opus)

Services / schemas / router: richer `ErratumInfo` / `ErratumOut` with approval
state, `errata_summary`, `erratum_for`, `record_type` search filter (+ parity
tests), `erratum_for_title` on search items; route and lifecycle tests (report
→ verify → reject; target digest untouched).

**Changes:**
- The reverse lookup returns published and candidate erratum rows for the
  target. Resolution uses the existing same-project-first rules in
  `domain/relationships.py`.
- `services/record_relationships.py`: `ErratumInfo` grows to `{id, kind, ref,
  type, section, reported_by, reported_date, original_html, corrected_html,
  notes_html, approval_state, digest}`. The approval state comes from
  `domain/approval.evaluate` over each erratum identity's decisions. Errata per
  ADR are few, so one `list_decisions` per erratum is acceptable; add a test
  that the query count stays bounded.
- `services/record_detail.py` + `schemas/records.py`:
  - `RecordDetailOut.errata` uses the richer `ErratumOut`.
  - New `errata_summary {total, verified, reported, rejected}` for the top
    notice.
  - On an erratum page: `erratum` (its content) and `erratum_for {id, title,
    uuid, resolved}`.
  - Drop the erratum's self "Corrects" entry from outbound links, since
    `erratum_for` replaces it.
- New `record_type` filter (`decision` default | `erratum` | `all`) through
  `SearchFilters` (storage port), `storage/postgres/search.py`,
  `services/search.py` and `routers/records.py`. It combines with
  `needs_approval`.
- Search items gain `erratum_for_title` when `record_kind` is `erratum`, via a
  cheap join or lookup.
- Update the parity tests.

### Task 4 — Seed and samples (model: sonnet)

Seed generator + samples converted to the new format (incl. an editorial
erratum and a pushed erratum candidate).

**Changes:**
- `seed_synthetic_gen.py`: generate errata in the new format.
- `samples/`: convert the sample erratum into
  `samples/adr-root/platform/doc/decisions/errata/…`.
- Add an editorial erratum, plus one pushed erratum candidate in
  `samples/candidates/` for the verify demo.

### Task 5 — Generate OpenAPI types (model: haiku)

Regenerate OpenAPI types (`npm run gen:types` with the backend running).

### Task 6 — Frontend layout (model: sonnet)

Frontend layout: two-column RecordView, `RecordSidebar`, `RecordStatusBanners`,
widened container, sidebar restyle of the existing cards; vitest tests.

**RecordView.vue** (page shell; keep it ≤ 300 lines):
- **Header (full width).** Title plus chips (Published/Candidate,
  Decision/Erratum). Below it, a new `RecordStatusBanners.vue` (prominent
  `v-alert`s with icon and text):
  - "This decision is obsoleted by <links>."
  - "This decision was updated by <links>."
  - "This decision has N errata (V verified, R reported)", linking to the
    errata section.
  - On an erratum: "This is an erratum for <ADR>" plus its status.
  - The existing freshness and digest-changed alerts
    (`RecordFreshnessBanner.vue`) stay here.
- **Two columns with `v-row` / `v-col`.** Main is `md="8"`, sidebar is
  `md="4"`. Below `md` the sidebar stacks after the main column. Widen the
  record page container (max-width about 1280px).
- **Main column:**
  - `RecordIssuesList`.
  - The document body (`RecordDecisionCard`, retitled per kind). For an
    erratum it is a new `ErratumBody.vue`: type/section line, then "Original
    text (says):", "Corrected text (should say):" and "Notes" as labelled
    blocks, without relying on colour alone.
  - New `ErrataSection.vue` (`id="errata"`): one `ErratumEntry.vue` per
    erratum, showing a status chip (Reported / Verified / Rejected, icon and
    text), type, section, the original vs corrected blocks, and a link to the
    erratum page. Rejected errata are collapsed by default.
  - `DivergenceBanner`, `ApprovalCard` (`id="approval"`) and `DiffPanel`.
- **Sidebar.** A new `RecordSidebar.vue` titled "About this decision" / "About
  this erratum". It composes the existing cards, restyled as compact sidebar
  sections:
  - an approval summary chip that links to `#approval`
  - `RecordMetadataCard`: the UUID in short form with copy, following the ux
    kit's technical-identifiers rule
  - `RecordProvenanceCard`, including freshness
  - `RecordLinksCard` (updates / obsoletes / referenced by)
  - `RecordSiblingsCard`
  - `LegacySignoffCard`

### Task 7 — Frontend errata UI (model: sonnet)

Frontend errata UI: `ErrataSection` / `ErratumEntry` / `ErratumBody`, erratum
labels in `labels.ts`, erratum wording in `ApprovalCard` / `DecisionDialog`,
search "Show" select + erratum rows; vitest tests.

**Changes:**
- `utils/labels.ts` gains `erratumStatusLabel(state)` and `erratumTypeLabel`.
  `ApprovalCard` and `DecisionDialog` use the erratum wording when the record
  is an erratum ("Verify erratum" / "Reject erratum"). The core decide logic
  in `useDecision` is unchanged.
- **Search.** A "Show" select (Decisions / Errata / Both) synced to the URL by
  `useSearchQuery` (`record_type`) and covered by Clear filters. Erratum rows
  get an "Erratum for <title>" line and chip.

### Task 8 — Documentation (model: sonnet)

Docs: `docs/schema.md` erratum section, `docs/approval.md` erratum statuses,
`docs/examples/README.md`, the `phase1-report.md` note.

### Task 9 — Playwright verification (model: sonnet)

Playwright verification run + screenshot re-shoots in `docs/demo/` + demo step
"report → verify an erratum".

### Task 10 — Independent review (model: opus)

Independent read-only review of the whole change against this plan.

### Task 11 — Fixes from review (model: mixed)

Fixes from task 10 (model per finding: haiku for typo/doc, sonnet for UI,
opus for backend logic).

### Task 12 — Final update (model: haiku)

Final STATUS / DECISIONS update and handoff notes.

## Execution

This is a post-Phase-1 change the product owner authorized. Work is linear, with
no worktrees, and the coordinator verifies and commits each task.

This parent session is the coordinator. It does no bulk implementation; it
dispatches each task above as a sub-agent with the listed model. Every prompt
is self-contained and tells the sub-agent to read `phases/README.md`,
`DECISIONS.md` and `10-ui-errata.md`, call `resolve_kits`, and not commit.

Tasks run one at a time in the main tree (no worktrees). Read-only reviewers
may run in parallel.

**Correctness gate after every task.** The coordinator itself:
- re-runs the task's checks (`task lint` / `task test` / `task build`,
  pyright, and migrations where touched);
- reads the critical diffs;
- looks at screenshots for UI tasks;
- sends failures back to the same agent via SendMessage, or to a fix agent;
- only then commits (Conventional Commits, agent author) and updates STATUS.

## Verification (coordinator)

```
task lint && task test && task build && pyright
alembic downgrade -1 && upgrade head
```

### Backend tests

- The new parser: all sections; missing corrected text; bad type; an old
  `kind: erratum` file gives `legacy_erratum_format`.
- Erratum listed on its target with approval state Reported, then Verified
  after accept, then Rejected after reject.
- An erratum never changes the target's digest or approval.
- A candidate erratum pushed from a branch shows as "proposed" on the target.
- Search `record_type` default excludes errata; `erratum` / `all` include them;
  it combines with `needs_approval`.
- Query count for detail with errata stays bounded.

### Frontend tests

- Sidebar holds metadata, provenance, links, revisions and legacy sign-off.
- Status banners show for obsoleted, updated and has-errata pages.
- Errata section rendering and status labels.
- Erratum page shows the says / should-say blocks.
- Search "Show" select and URL sync.

### Playwright verification

Run on `catalog.demo.yaml` with dev login:
- an obsoleted ADR shows the top banner
- the ADR with errata shows the notice and inline errata
- the erratum page
- push an erratum candidate, verify it as a reviewer, and confirm the target
  shows it as Verified
- at 390px the sidebar stacks below the body with no horizontal scroll
- no console errors

## Definition of done

All 12 tasks complete. All verification checks pass (lint, test, build, pyright,
database migration round-trip). Playwright tests pass. Screenshots updated in
`docs/demo/`. STATUS and DECISIONS updated. Coordinator commits and presents
the summary to the user, then **stops**.
