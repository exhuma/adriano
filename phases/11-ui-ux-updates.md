# Phase 11 — UI/UX updates from the desktop review

## Goal

Act on the desktop UI/UX review in `docs/ui-review/README.md`. The phase
should:

- fix contrast and accessibility defects
- put the shell and pages on one alignment grid
- bring the reviewer's main action within reach
- demote or hide elements that are too prominent or that repeat information

It also delivers two small backend additions the product owner asked for:

- a "Recently changed" sort for search
- a dev-only endpoint that feeds the dev-login role presets

## Prerequisites

- Phases 01–10 are `done`.
- Product-owner decisions: recorded below under "Decisions" (2026-10-20).

## Context to read

- `phases/README.md`, `phases/DECISIONS.md` and `phases/STATUS.md`.
- `docs/ui-review/README.md`: the findings, IDs, evidence and screenshots.
  Each task below lists the finding IDs it closes.
- Quartermaster kits:
  - `module-ux-principles`, sections `accessibility-wcag`, `ui-modes` and
    `fitts-hicks-laws`
  - `module-vue-vuetify`, sections `vuetify-theming`, `mode-indicators` and
    `loading-feedback`
  - `module-fastapi`, sections `layering` and `testing-pytest` (Tasks 7
    and 10)

## Decisions (product owner, 2026-10-20)

1. **Health chip:** hidden while the backend is healthy, for every role.
   It appears automatically when the backend is degraded or offline.
2. **"Pending approval" on search rows:** neutral text or icon. Strong
   colour is reserved for issues and rejection.
3. **Sources for readers:** still visible, but simplified. Operator-only
   detail is shown only to users with `operate`: env-var names, recovery
   steps and poll actions.
4. **Search sort:** add a sort control. The options are:
   - **Relevance:** only when a query is set; it is the default then.
   - **Title A–Z:** the default without a query.
   - **Recently changed:** ordered by `record.updated_at`, newest first.
5. **Dev-login presets:** read from the loaded catalog through a dev-only
   endpoint, mounted under the same flag as `POST /auth/dev/token`. It must
   never reach a production build.
6. **Theme choice:** light/dark/system in a user menu. The default follows
   the OS. The choice is remembered per browser (local storage, wrapped in
   try/catch); nothing is stored on the server.

## Vuetify first (binding for every task)

The project uses Vuetify (see `CLAUDE.md`). Every visual change must use
Vuetify's own theming and defaults before any custom CSS.

Work down this ladder, and stop at the first step that can express the
change:

1. **Theme** (`plugins/vuetify.ts`, `theme.themes.*`):
   - **Colours:** semantic colours, plus custom semantic keys where one is
     needed (for example a contrast-safe status-text colour).
   - **Theme `variables`:** `border-color`, `border-opacity`,
     `high-emphasis-opacity`, `medium-emphasis-opacity`, overlay
     multipliers.
   - **Theme selection:** `defaultTheme: "system"`, switched at runtime
     through `useTheme()` (`theme.change(...)`).
2. **Global defaults** (`createVuetify({ defaults })`):
   - Per-component prop defaults (`VCard`, `VChip`, `VAlert`, `VBtn`,
     `VTextField`, `VSelect`, `VContainer`, `VDialog` and others).
   - Component **aliases** with their own defaults (for example a
     `VStatusChip` alias of `VChip`, or a `VSidebarCard` alias of `VCard`).
   - Nested defaults (for example `VCard: { VCardTitle: { … } }`).
3. **Scoped defaults:** `<v-defaults-provider>` for one region (for example
   a compact sidebar, or a dense filter bar).
4. **Component props and Vuetify utility classes:**
   - spacing (`ma-*`, `pa-*`, `ga-*`)
   - flex and alignment (`d-flex`, `align-*`, `justify-*`)
   - typography (`text-h*`, `text-body-*`, `font-weight-*`,
     `text-medium-emphasis`)
   - position (`position-sticky`)
   - visibility (`d-sr-only`)
   - layout components (`v-container`, `v-row`, `v-col`, `v-sheet`,
     `v-toolbar`) and dimension props (`max-width` and friends)
5. **Vuetify SASS settings:** a `settings.scss` wired through
   `vite-plugin-vuetify`'s `styles.configFile`. Only for values that
   Vuetify exposes as SASS variables and that steps 1–4 cannot reach
   (for example the typography map).
6. **Custom scoped CSS, last resort:**
   - Only theme variables are allowed (`rgb(var(--v-theme-…))`,
     `var(--v-layout-top)`, and so on).
   - Every rule carries a one-line comment explaining why steps 1–5 could
     not express it.

Rules:

- Do not add a global stylesheet or design-token file outside the Vuetify
  theme. No hex, rgb or named colours outside `plugins/vuetify.ts`.
- When a task touches a component that already has a `<style>` block (24
  files today), replace the rules Vuetify can express (for example the
  `.sr-only` copies with `d-sr-only`, flex layouts with utility classes),
  and justify any rule that stays.
- Set a prop at the call site only when that instance has to differ from
  the global default.

### How each fix maps to Vuetify mechanisms

| Finding | Mechanism |
|---|---|
| G-01 contrast | theme colours (contrast-safe light status colours) |
| G-03 page width | `defaults.VContainer.maxWidth`; drop `meta.wide` |
| G-02 app-bar alignment | `v-container` (same default) inside `v-app-bar` |
| G-05 headings | nested defaults for `VCardTitle` (`tag`, classes) |
| G-06 dark theme | `defaultTheme: "system"` plus `useTheme().change()` |
| G-07 card outlines | `defaults.VCard` (`variant: "flat"`, `border: true`) |
| G-07 card outlines | theme `border-opacity` |
| G-08 focus ring | Vuetify focus styles; CSS only for what is missing |
| G-09 empty alerts | `defaults.VTextField/VSelect.hideDetails: "auto"` |
| G-11 `.sr-only` | `d-sr-only` utility class |
| S-03 filter bar | `<v-defaults-provider>` with one `density` |
| S-04 filter chips | `v-chip` `closable`, `variant` from defaults |
| R-01 sticky sidebar | `position-sticky`; top offset via `--v-layout-top` |
| R-07 prose size | `text-body-1` and a `max-width` prop |
| O-05 table headers | `VTable` defaults or header-slot classes |

## Design

### Layout grid

- **One page width** for every route, about 1280–1440 px max, set through
  the `VContainer` default. Drop `meta.wide`. The app bar wraps its content
  in a `v-container` with the same default, so the brand, nav and
  right-hand cluster line up with the content edges (G-02, G-03).
- **Nav** goes left-aligned straight after the brand.
- **Record page:**
  - Main and sidebar columns start on the same top line (R-06).
  - The sidebar is sticky at `md` and up (R-01).
  - Prose is capped at about 70ch at body-1 size (R-07).
- **Search:**
  - The filter bar is one `<v-defaults-provider>` density with shared top
    lines (S-03).
  - Status sits inline in the row's metadata line, left-aligned (S-01).

### Prominence

Apply the verdict column of the "Prominence audit" table in the review.
The principles:

- Show a status chip only when it differs from the default.
- Reserve strong colour for errors, warnings and rejections.
- Use alerts only for things the user has to act on or be warned about.
- Say each fact once per page.

### Accessibility

- **Contrast:** contrast-safe status colours in the light theme, with every
  text pair at 4.5:1 or more (G-01).
- **Focus:** a visible focus ring on every control (G-08).
- **Headings:** a real heading hierarchy, with card titles rendered as
  headings (G-05).
- **Dialogs:** each dialog is named (D-01).
- **Clean-up:** no empty live regions (G-09), and no tab stops on static
  content (G-10).
- **Theme:** the system theme by default (G-06).

### Interaction

- Decision actions sit in the sidebar's first card (R-01).
- A persistent row of active-filter chips appears under the search bar
  (S-04). Ordering and clearing logic lives in a Vue-free TypeScript module,
  per the mode-indicators rules.
- A sort control with Relevance, Title A–Z and Recently changed (S-08). The
  sort is kept in the URL (`sort=`), like the other filters.
- Human-worded reason copy (R-10). Records that cannot be decided show as
  "Blocked" (R-02).
- Dialogs name the record they act on (D-02).

## Tasks

Run the tasks in order. Every frontend task adds or updates vitest tests for
the behaviour it changes, mirroring `src/` under `frontend/tests/`. Every
frontend task follows "Vuetify first" and lists, in its hand-back, every
custom CSS rule it added or kept and why.

### Task 0 — Documentation and planning (model: haiku)

- Record the decisions above, the single page width, the chip-visibility
  rule and the "Vuetify first" ladder in `DECISIONS.md`. `CLAUDE.md`
  already carries the rule.

### Task 1 — Theme and global defaults (model: sonnet)

**Closes:** G-01, G-05 (the scale), G-06, G-07, G-08, G-09 (globally).

**Files:** `plugins/vuetify.ts`, `StatusChip.vue`, and a theme composable
for the user's choice.

**Theme:**
- Light-theme status colours that pass on their tonal tint, adding a custom
  semantic key if a separate fill colour has to stay bright.
- `border-opacity` and the emphasis variables.
- `defaultTheme: "system"`.

**Defaults:**
- `VCard`: flat with a border.
- `VChip`: tonal and small. `StatusChip` then relies on the defaults or an
  alias instead of hard-coded props.
- `VTextField` and `VSelect`: `hideDetails: "auto"`.
- `VContainer`: `maxWidth`.
- `VCardTitle`: heading tag and classes, through nested defaults.

**Other:**
- A `useThemePreference` composable (light/dark/system, local storage in
  try/catch).
- Focus ring: use Vuetify's focus styles. Add a theme-variable CSS rule
  only where controls lack a visible ring, with a justification comment.

**Tests:**
- A vitest test computes the contrast of every theme text/background pair,
  including the 12% tonal tint, and asserts at least 4.5:1.
- The preference composable, including a fallback when storage throws.

### Task 2 — App shell (model: sonnet)

**Closes:** G-02, G-03, G-04, A-01.

**Files:** `App.vue`, `AppBarMenu.vue`, `SignInScreen.vue`,
`router/index.ts`.

- A `v-container` inside the app bar; remove `meta.wide` and the
  `.container--wide` CSS.
- Nav left-aligned after the brand.
- The health chip is shown only when the backend is not OK (decision 1).
- The dev-login chip is restyled through the theme or defaults and stays
  persistent.
- A user menu (`v-menu`) holds the display name, the theme choice and
  sign-out.
- The sign-in button uses the primary colour.

### Task 3 — Search results list (model: sonnet)

**Closes:** S-01, S-02, S-05, S-07.

**Files:** `SearchView.vue`, `utils/labels.ts`.

- Row layout: title on line 1; source/project, short status and issue
  chips on line 2, left-aligned, using utility classes.
- Show only chips that differ from the default. Pending approval becomes
  neutral text or an icon (decision 2).
- Keep chip text to 1–2 words, with the branch as secondary text.
- "Clear search and filters" label, and the empty-state title as a heading.

### Task 4 — Search filter bar, active-filter row and sort UI (model: sonnet)

**Closes:** S-03, S-04, S-06 and the S-08 UI.

**Files:** `SearchView.vue`, `composables/useSearchQuery.ts`, and a new
pure-TS `activeFilters` module.

- An aligned filter bar inside a `<v-defaults-provider>`, a capped search
  width (`max-width` prop), and the switch hint in a `v-tooltip`.
- The active-filter chip row: `role=status aria-live=polite`, closable
  chips, and a non-warning colour.
- The count line mentions the active filters.
- A sort `v-select`:
  - Relevance appears only when a query is set.
  - `sort` is kept in the URL.
  - It is built against the API from Task 7. If Task 7 is not done yet,
    stub the param and finish the wiring after Task 7.
- Unit-test the active-filter module (ordering, clearing one filter) and
  the `sort` URL sync.

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
- Body-1 prose at about 70ch.
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
- The sidebar is sticky through `position-sticky`, with the top offset from
  `--v-layout-top`.
- Columns share a top line.
- Card titles become headings.
- Truncated values wrap and get copy buttons.
- The Diff card is hidden when there is no prior revision.
- Provenance is no longer a tab stop.
- Keep `RecordView.vue` at 300 lines or less.

### Task 7 — Search sort API (model: opus)

**Closes:** the S-08 backend.

**Files:**
- `backend/app/routers/records.py` (search route)
- `services/search.py`
- `storage/postgres/search.py`
- the storage port
- the OpenAPI types (`npm run` generator)

Changes:
- Add `sort: relevance | title | recent`:
  - The default is `relevance` when a query is set, otherwise `title`.
  - `relevance` without a query falls back to `title`.
  - `recent` orders by `record.updated_at` descending, then title, then id,
    so pages are stable.
- First confirm in code that `updated_at` changes only when content
  changes. `last_seen_at` is the poll heartbeat. If `updated_at` turns out
  to mean something else, stop and report back.
- Keep the needs-approval page query consistent with the new key order.
- Add an index migration only if `EXPLAIN` on the seeded data shows a
  sequential sort on a large set. Otherwise document why none is needed.
- Pytest:
  - each sort
  - the defaults
  - stable pagination with equal timestamps
  - combination with `needs_approval` and `record_type`

### Task 8 — Human copy and blocked status (model: sonnet)

**Closes:** R-02, R-10, O-04 (copy and role gating).

**Files:** `utils/labels.ts`, `ApprovalCard.vue`, `SourceProblemCell.vue`,
`SourcesView.vue`.

- Map every decide-blocker reason code, and every validation and poll
  problem code, to a plain-language message.
- Add a "Blocked" display status for content that cannot be decided.
- Sources for readers (decision 3): status and dates only. The env-var and
  recovery detail is shown when the user can `operate`.
- Test the label mapping for every code, and the role gating.
- If a reason code is not available in the API types, stop and report back
  rather than parsing message strings.

### Task 9 — Dialogs (model: sonnet)

**Closes:** D-01, D-02, D-03, R-12.

**Files:** `DecisionDialog.vue`, `DevLoginDialog.vue`, `RecordLinksCard.vue`.

- `aria-labelledby`, with the title rendered as a heading.
- Dialogs name the record.
- Short digest with a copy button and a "Show full digest" disclosure.
- Aligned padding through `VCardTitle` / `VCardText` defaults.
- Short UUIDs in the links card.

### Task 10 — Dev-login presets from config (model: opus)

**Closes:** D-04.

**Backend:**
- Add `GET /auth/dev/roles` to `routers/auth_dev.py`, mounted only when
  `ADRIANO_DEV_AUTH_ENABLED`.
- It returns the role names from the loaded catalog:
  - the `rbac` roles, each with its permissions
  - the reviewer roles from `approval_policy`
- Pytest:
  - the route is absent when dev auth is off
  - the response shape

**Frontend:**
- Add a `src/api/devAuth.ts` call, imported only from `auth/devAuth.ts`, so
  the existing build-time isolation and `scripts/check-no-dev-auth.sh` still
  hold.
- `DevLoginDialog` derives its presets:
  - **Reader:** the roles that grant `read` only.
  - **Reviewer:** read plus an approval-policy role.
  - **Operator:** a role with `operate`.
- Presets the catalog cannot satisfy are hidden.
- Vitest covers preset derivation.

### Task 11 — Sources (model: sonnet)

**Closes:** O-01, O-02, O-03, O-05, O-04 (layout).

**Files:** `SourcesView.vue`, `SourceProblemCell.vue`.

- One status chip per row.
- A default-size "Poll now" button.
- The problem detail shown next to the status, or as a sub-row under a
  failing source.
- Relative dates with the absolute date in a `v-tooltip`.
- Header weight through defaults or classes.
- The permission hint moves below the table.

### Task 12 — Custom CSS clean-up (model: sonnet)

**Closes:** G-11 and the rest of the "Vuetify first" audit.

- Go through every remaining `<style>` block.
- Replace what Vuetify can express:
  - `.sr-only` with `d-sr-only`
  - empty/error/loading-state flex layouts with utility classes
  - hard px values with props
- Add `aria-hidden` to the decorative icon in `ErrorState`.
- Hand back a list of the rules that remain, each with its justification.

### Task 13 — Demo screenshots (model: sonnet)

Re-shoot the `docs/demo/` screenshots that show changed screens, and update
`docs/demo/README.md` wherever the wording changed.

### Task 14 — Playwright re-verification (model: sonnet)

Re-run the review's method (see "Method" in `docs/ui-review/README.md`) at
1366, 1920 and 2560, in dark mode, and at 200% zoom. Assert the checklist
under "Playwright verification" below.

Put the new screenshots next to the old ones in `docs/ui-review/` with an
`after-` prefix, and add an "After" section to that README.

### Task 15 — Independent review (model: opus)

A read-only review of the whole change against this plan, the review's
finding IDs and the "Vuetify first" ladder. Flag any custom CSS whose
justification doesn't hold.

### Task 16 — Fixes from review (model: mixed)

Fix what Task 15 finds:

- haiku for copy or docs
- sonnet for UI
- opus for anything touching the API or backend

### Task 17 — Final update (model: haiku)

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
  - follow "Vuetify first"
  - not commit

**Correctness gate after every task.** The coordinator:

- re-runs `task lint`, `task test` and `task build` (plus pyright and the
  migration round-trip for Tasks 7 and 10)
- reads the diffs, including every added or changed `<style>` rule
- looks at screenshots of the screens the task touched
- only then commits (Conventional Commits, agent author) and updates
  `STATUS.md`

**Data safety.** Do not run `task dev` or `task db:up` against a database
with test data. Start `task dev:backend` and `task dev:frontend` on their
own.

Dev sign-in roles for the local `catalog.yaml`, until Task 10 lands:

- reader: `adr-reader`
- reviewer: `adr-reader, adr-reviewer`
- operator: `admin`

## Verification (coordinator)

```
task lint && task test && task build && pyright
alembic downgrade -1 && alembic upgrade head   # only if Task 7 adds one
```

### Backend tests

- Search `sort`:
  - each value
  - the defaults with and without a query
  - stable pagination
  - combination with `needs_approval` and `record_type`
- `GET /auth/dev/roles`:
  - present only with dev auth enabled
  - returns the rbac roles and the reviewer roles

### Frontend tests

- Every theme text/background pair, including the tonal tints, reaches at
  least 4.5:1 in light and dark.
- Theme preference: system by default, the stored choice applied, and
  storage errors tolerated.
- The active-filter module: chip order, clearing one filter, and the
  live-region text. `sort` stays in sync with the URL.
- The chip-visibility rule: no chip for Published, and neutral pending.
- Label mapping for every reason and problem code, including "Blocked".
  Reader gating on Sources.
- The sidebar shows Accept/Reject only when `can_decide`, and focus returns
  to the trigger after the dialog closes.
- Dialogs have an accessible name, and the record title appears in the
  dialog.
- Dev-login preset derivation from the roles response.

### Static checks

- No hex, rgb or named colours outside `plugins/vuetify.ts`.
- Every `<style>` rule left in `src/` has a justification comment.
- `scripts/check-no-dev-auth.sh` passes on the production build.

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
  applied, and the user-menu choice overrides it.

**Zoom**
- At 200% (683×384 at DPR 2): no page-level horizontal scroll, and the
  Sources problem detail is visible without scrolling the table.

**Search**
- "Recently changed" puts the most recently updated record first.

**Dev sign-in**
- Each preset signs in without a 403 on both `catalog.yaml` and
  `catalog.demo.yaml`.

**Console and data**
- No console errors, apart from Vite dependency-optimisation reloads.
- Database row counts are the same before and after the run.

## Definition of done

- Every task is complete, and every finding of severity 2 or more in
  `docs/ui-review/README.md` is closed or recorded in `DECISIONS.md` as
  deferred, with a reason.
- All checks pass, including the static checks.
- The `docs/demo/` and `docs/ui-review/after-*` screenshots are updated.
- `STATUS.md` and `DECISIONS.md` are updated.
