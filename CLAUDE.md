# CLAUDE.md

## Quartermaster instruction kits

This project relies on the `quartermaster` MCP server for architecture, tooling and
capability guidance. Kits are loaded on demand — never copy kit files into the repo,
and don't keep a fixed kit list here.

- Before making or planning any change, call `resolve_kits(task="<plain-language description>")`
  and follow the returned guidance (its `always_load` sections are inlined).
- Re-run `resolve_kits` whenever:
  - the user asks for a new change or plan;
  - you start a new feature, subsystem, or aspect of the work;
  - the task's direction shifts or new traits come into scope (e.g. "add login" → OIDC);
  - you resume after a context compaction, before the next edit.
- Use `get_kit` / `search_kit_content` to pull additional kit sections when needed.
- If no kit covers what you need, or guidance is ambiguous, use
  `request_clarification_or_addition` (check `check_existing_gap_issue` first).

## UI route

The frontend uses Vuetify (quartermaster `stack-fastapi-vuetify`, which
composes `module-fastapi` and `module-vue-vuetify`), not the
`module-vue-ui-toolbelt` Reka UI + plain CSS route: the catalog's record
and sources screens need data-table-like list/filter components and
Material Design is an acceptable look for an internal governance tool,
so Vuetify's ready-made components outweigh hand-rolled ARIA primitives.

**Vuetify first.** Before writing any custom CSS, use Vuetify's own
mechanisms, in this order:

1. theme colours and variables
2. global `defaults` and aliases in `createVuetify`
3. `<v-defaults-provider>`
4. component props and utility classes
5. Vuetify SASS settings

Custom scoped CSS is the last resort. It may use only theme variables, and
each rule needs a comment saying why Vuetify could not express it. See
`phases/11-ui-ux-updates.md`, "Vuetify first".
