# Phase 11 — UI/UX updates from the desktop review

## Goal

Act on the desktop UI/UX review in `docs/ui-review/README.md`. The phase
should:

- fix contrast and accessibility defects
- put the shell and pages on one alignment grid
- bring the reviewer's main action within reach
- demote or hide elements that are too prominent or that repeat information

There are no backend behaviour changes. Any backend work is limited to
exposing data the UI already receives.

## Prerequisites

- Phases 01–10 are `done`.
- The product owner has answered the open questions at the end of this file,
  or accepted the defaults listed there.

## Context to read

- `phases/README.md`, `phases/DECISIONS.md` and `phases/STATUS.md`.
- `docs/ui-review/README.md`: the findings, IDs, evidence and screenshots.
  Each task below lists the finding IDs it closes.
- Quartermaster kits:
  - `module-ux-principles`, sections `accessibility-wcag`, `ui-modes` and
    `fitts-hicks-laws`
  - `module-vue-vuetify`, sections `vuetify-theming`, `mode-indicators` and
    `loading-feedback`

## Design

### Layout grid

- **One page width** for every route, about 1280–1440 px max, through a
  single shared container. Drop `meta.wide`. The app-bar content uses the
  same container, so the brand, the nav and the right-hand cluster line up
  with the content edges (G-02, G-03).
- **Nav** goes left-aligned straight after the brand.
- **Record page:**
  - Main and sidebar columns start on the same top line (R-06).
  - The sidebar is sticky at `md` and up, offset by the app-bar height
    (R-01).
  - Prose is capped at about 70ch at 16 px (R-07).
- **Search:**
  - The filter bar uses one density with shared top lines (S-03).
  - Status sits inline in the row's metadata line, left-aligned (S-01).

### Prominence

Apply the verdict column of the "Prominence audit" table in the review.
The principles:

- Show a status chip only when it differs from the default.
- Reserve strong colour for errors, warnings and rejections.
- Use alerts only for things the user has to act on or be warned about.
- Say each fact once per page.

### Accessibility

- **Contrast:** contrast-safe light-theme status tokens, with every text
  pair at 4.5:1 or more (G-01).
- **Focus:** a global `:focus-visible` ring (G-08).
- **Headings:** a real heading hierarchy, with every card title rendered as
  a heading (G-05).
- **Dialogs:** each dialog is named (D-01).
- **Clean-up:** no empty live regions (G-09), and no tab stops on static
  content (G-10).
- **Theme:** follow the OS, with a light/dark/system choice (G-06).

### Interaction

- Decision actions sit in the sidebar's first card (R-01).
- A persistent row of active-filter chips appears under the search bar
  (S-04). Ordering and clearing logic lives in a Vue-free TypeScript module,
  per the mode-indicators rules.
- Human-worded reason copy (R-10). Records that cannot be decided show as
  "Blocked" (R-02).
- Dialogs name the record they act on (D-02).

## Tasks

Run the tasks in order. Every frontend task adds or updates vitest tests for
the behaviour it changes, mirroring `src/` under `frontend/tests/`.

### Task 0 — Documentation and planning (model: haiku)

Record in `DECISIONS.md`:

- the answers to the open questions
- the single page width
- the chip-visibility rule

### Task 1 — Theme, tokens and type scale (model: sonnet)

**Closes:** G-01, G-05 (the scale), G-06, G-07, G-08.

**Files:** `plugins/vuetify.ts`, `StatusChip.vue`, the `App.vue` styles, and
the card variants across `components/record/*`.

- Add contrast-safe status colours for the light theme. Write a vitest test
  that computes the contrast of every theme text/background pair (including
  the 12% tonal tint) and asserts at least 4.5:1.
- Follow `prefers-color-scheme`, and add a light/dark/system choice. It
  lives in the user menu from Task 2, and the choice is kept in browser
  storage, wrapped in try/catch.
- One card style: a low-emphasis border, and a single surface in dark mode.
- A global `:focus-visible` outline.
- A type scale applied to h1, h2 and h3.

### Task 2 — App shell (model: sonnet)

**Closes:** G-02, G-03, G-04, A-01.

**Files:** `App.vue`, `AppBarMenu.vue`, `SignInScreen.vue`,
`router/index.ts`.

- A shared container for the app bar and main content, and remove
  `meta.wide`.
- Nav left-aligned after the brand.
- The health chip is shown only when the backend is not OK.
- The dev-login chip is restyled with a passing contrast pair and stays
  persistent.
- The user name and sign-out move into a user menu, together with the theme
  choice from Task 1.
- The sign-in button uses the primary colour.

### Task 3 — Search results list (model: sonnet)

**Closes:** S-01, S-02, S-05, S-07.

**Files:** `SearchView.vue`, `utils/labels.ts`.

- Row layout: title on line 1; source/project, short status and issue chips
  on line 2, left-aligned.
- Show only chips that differ from the default.
- Keep chip text to 1–2 words, with the branch as secondary text.
- "Clear search and filters" label, and the empty-state title as a heading.

### Task 4 — Search filter bar and active-filter row (model: sonnet)

**Closes:** S-03, S-04, S-06, G-09 (search).

**Files:** `SearchView.vue`, `composables/useSearchQuery.ts`, and a new
pure-TS `activeFilters` module.

- An aligned filter bar with a capped search width and the switch hint in
  a tooltip.
- The active-filter chip row: `role=status aria-live=polite`, closable
  chips, and a non-warning colour.
- The count line mentions the active filters.
- `hide-details` where a field has no message.
- Unit-test the active-filter module: ordering, and clearing one filter.

### Task 5 — Record header, banners and body (model: sonnet)

**Closes:** R-03, R-04, R-05, R-07, R-11, R-13.

**Files:**
- `RecordHeader.vue`, `RecordStatusBanners.vue`, `RecordFreshnessBanner.vue`
- `RecordDecisionCard.vue`, `ErratumBody.vue`, `ErrataSection.vue`

Changes:
- One lifecycle notice, not shown in the error colour.
- An errata link in the header meta line.
- No duplicate title.
- Non-default chips only.
- 16 px prose at about 70ch.
- An errata count without "(0)".

### Task 6 — Record layout and decision reach (model: opus)

**Closes:** R-01, R-06, R-08, R-09, G-05 (card headings), G-10.

**Files:**
- `RecordView.vue`, `RecordSidebar.vue`, `ApprovalCard.vue`
- `RecordProvenanceCard.vue`, `RecordIssuesList.vue`, `DiffPanel.vue`
- the sidebar cards

Changes:
- The sidebar's first card holds the status, plus Accept/Reject when
  `can_decide`. Both sets of buttons reuse the existing focus-return
  handling.
- The sidebar is sticky at `md` and up.
- Columns share a top line.
- Card titles become headings.
- Truncated values wrap and get copy buttons.
- The Diff card is hidden when there is no prior revision.
- Provenance is no longer a tab stop.
- Keep `RecordView.vue` at 300 lines or less.

### Task 7 — Human copy and blocked status (model: sonnet)

**Closes:** R-02, R-10, O-04 (copy).

**Files:** `utils/labels.ts`, `ApprovalCard.vue`, `SourceProblemCell.vue`.

- Map every decide-blocker reason code, and every validation and poll
  problem code, to a plain-language message.
- Add a "Blocked" display status for content that cannot be decided.
- Test the label mapping for every code.
- If a reason code is not available in the API types, stop and report back
  rather than parsing message strings.

### Task 8 — Dialogs (model: sonnet)

**Closes:** D-01, D-02, D-03, D-04, R-12.

**Files:** `DecisionDialog.vue`, `DevLoginDialog.vue`, `RecordLinksCard.vue`.

- `aria-labelledby`, with the title rendered as a heading.
- Dialogs name the record.
- Short digest with a copy button and a "Show full digest" disclosure.
- Aligned padding.
- Dev-login presets that match the catalogs (see open questions).
- Short UUIDs in the links card.

### Task 9 — Sources (model: sonnet)

**Closes:** O-01, O-02, O-03, O-05, O-04 (layout).

**Files:** `SourcesView.vue`, `SourceProblemCell.vue`.

- One status chip per row.
- A default-size "Poll now" button.
- The problem detail shown next to the status, or as a sub-row under a
  failing source.
- Relative dates with the absolute date in a tooltip.
- Medium-weight headers.
- The permission hint moves below the table.

### Task 10 — Shared utilities and a11y clean-up (model: haiku)

**Closes:** G-09 (rest), G-11.

- One shared `.sr-only` utility.
- `hide-details` on the remaining fields.
- `aria-hidden` on the decorative icon in `ErrorState`.

### Task 11 — Demo screenshots (model: sonnet)

Re-shoot the `docs/demo/` screenshots that show changed screens, and update
`docs/demo/README.md` wherever the wording changed.

### Task 12 — Playwright re-verification (model: sonnet)

Re-run the review's method (see "Method" in `docs/ui-review/README.md`) at
1366, 1920 and 2560, in dark mode, and at 200% zoom. Assert the
checklist under "Playwright verification" below.

Put the new screenshots next to the old ones in `docs/ui-review/` with an
`after-` prefix, and add an "After" section to that README.

### Task 13 — Independent review (model: opus)

A read-only review of the whole change against this plan and the review's
finding IDs.

### Task 14 — Fixes from review (model: mixed)

Fix what Task 13 finds:

- haiku for copy or docs
- sonnet for UI
- opus for anything touching the API types or backend

### Task 15 — Final update (model: haiku)

Update `STATUS.md` and `DECISIONS.md`, and write the handoff notes.

## Execution

This is a post-Phase-1 change; it starts only after the product owner
authorises it.

- The parent session is the coordinator and dispatches each task as a
  sub-agent with the listed model.
- Tasks run linearly in the main tree: no worktrees, and never two writing
  agents at once.
- Every prompt tells the sub-agent to:
  - read `phases/README.md`, `DECISIONS.md`, this file and
    `docs/ui-review/README.md`
  - call `resolve_kits`
  - not commit

**Correctness gate after every task.** The coordinator:

- re-runs `task lint`, `task test` and `task build`
- reads the diffs
- looks at screenshots of the screens the task touched
- only then commits (Conventional Commits, agent author) and updates
  `STATUS.md`

**Data safety.** Do not run `task dev` or `task db:up` against a database
with test data. Start `task dev:backend` and `task dev:frontend` on their
own.

Dev sign-in roles for the local `catalog.yaml`:

- reader: `adr-reader`
- reviewer: `adr-reader, adr-reviewer`
- operator: `admin`

## Verification (coordinator)

```
task lint && task test && task build
```

### Frontend tests

- Every theme text/background pair, including the tonal tints, reaches at
  least 4.5:1 in light and dark.
- The active-filter module: chip order, clearing one filter, and the
  live-region text.
- The chip-visibility rule: no chip for Published, a chip for every
  non-default state.
- Label mapping for every reason and problem code, including the "Blocked"
  status.
- The sidebar shows Accept/Reject only when `can_decide`, and focus returns
  to the trigger after the dialog closes.
- Dialogs have an accessible name, and the record title appears in the
  dialog.

### Playwright verification

Run against the local test data with dev sign-in, at 1366, 1920 and 2560
unless a check says otherwise.

**Alignment**
- The app-bar brand's left edge equals the content container's left edge,
  within 1 px, on search, a record and sources.
- The container's left edge is identical across routes.

**Targets**
- No interactive target is smaller than 24×24 px.
- The record page's Accept/Reject are visible without scrolling at
  1366×768.

**Contrast**
- No text node below 4.5:1 (3:1 for large text), computed with the tonal
  underlay composited, in both themes.

**Keyboard**
- The skip link comes first.
- Every control shows a visible focus ring.
- No static content is a tab stop.
- Escape and Cancel return focus to the trigger.

**Theme**
- With the OS set to dark (`colorScheme: 'dark'`), the dark theme is
  applied.

**Zoom**
- At 200% (683×384 at DPR 2): no page-level horizontal scroll, and the
  Sources problem detail is visible without scrolling the table.

**Console**
- No console errors, apart from Vite dependency-optimisation reloads.

**Data**
- Database row counts are the same before and after the run.

## Definition of done

- Every task is complete, and every finding of severity 2 or more in
  `docs/ui-review/README.md` is closed or recorded in `DECISIONS.md` as
  deferred, with a reason.
- All checks pass.
- The `docs/demo/` and `docs/ui-review/after-*` screenshots are updated.
- `STATUS.md` and `DECISIONS.md` are updated.

## Open questions (product owner)

Defaults in **bold** apply if there is no answer.

1. **Health chip:** **hide while healthy, for every role**; or keep showing
   it to operators?
2. **"Pending approval" on rows:** **neutral text or icon**; or hide it
   entirely and rely on the Needs-approval filter?
3. **Sources page for readers:** **visible, without env-var detail**;
   visible as it is now; or hidden from the nav?
4. **Sort order for search:** **alphabetical, labelled "A–Z"**; or add
   "Recently changed" as an option (S-08, needs an API field)?
5. **Dev-login presets:** **update them to match both catalogs' role
   names**; or read them from the loaded config through a dev-only
   endpoint?
6. **Theme choice:** **in the user menu, kept per browser**; or stored
   server-side per user?
