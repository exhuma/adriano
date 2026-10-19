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
