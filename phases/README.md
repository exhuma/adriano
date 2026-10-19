# Implementation phases — coordinator protocol

This folder drives the implementation of **Product Phase 1** of the ADR
governance catalog ("adriano"). Any session, including one that starts
empty, can continue the work by following this file.

Files:

- `SPEC.md` — verbatim product specification (source of truth for
  requirements and the 27 Phase 1 acceptance criteria).
- `DECISIONS.md` — decisions confirmed with the product owner, plus the
  architecture, schema, and API contract every phase must follow.
- `STATUS.md` — progress table and handoff notes. Update after every
  phase.
- `01-*.md` … `09-*.md` — one self-contained prompt per implementation
  phase.

Note: the numbered files are *implementation phases* of Product Phase 1.
They are not the product "Phase 2+" backlog from the spec, which must not
be started without explicit product-owner authorization.

## Coordinator (the main session)

The main session coordinates and verifies; sub-agents implement.

1. Read `STATUS.md`. Pick the first phase whose status is not `done`.
   If a phase is `in-progress`, read its handoff notes and resume at the
   first unfinished task.
2. Call quartermaster `resolve_kits(task="<phase goal>")` as required by
   `CLAUDE.md`.
3. Run the phase's sub-agent tasks **strictly in the listed order**,
   one at a time, using the `Agent` tool with the listed `model`
   (`opus` or `sonnet`; `haiku` only for trivial edits such as a typo or
   a STATUS line). Use `subagent_type: "general-purpose"`.
   - **Never** use git worktrees (`isolation` must be omitted).
   - **Never** run two writing sub-agents concurrently. Read-only
     reviewers (e.g. `Explore`) may run in parallel.
4. Each sub-agent prompt must be self-contained. Use this template:

   ```text
   You are implementing part of the "adriano" ADR catalog in
   /home/exhuma/work/adriano (main working tree; no worktrees).
   Before editing:
   1. Read phases/README.md (section "Sub-agent rules"),
      phases/DECISIONS.md, and phases/NN-<name>.md.
   2. Read the SPEC.md sections named in your task.
   3. Call quartermaster resolve_kits(task="<your task>") and follow the
      returned guidance (load extra sections with get_kit when needed).
   Then perform task <K> of phases/NN-<name>.md.
   Handoff notes from earlier phases:
   <paste relevant STATUS.md notes>
   Finish with: files changed, commands run and their results,
   deviations from DECISIONS.md, open issues.
   ```

5. After each sub-agent finishes, the coordinator **itself** runs the
   phase's verification commands. On failure, send the failure output
   back to the same agent (`SendMessage`) or dispatch a fix agent. A
   phase is never marked `done` with red checks.
6. When a phase is done:
   - Commit with Conventional Commits, atomic where practical, with the
     agent identified as the author (see "Commit identity" below).
   - Update `STATUS.md`: status `done`, commit hash, handoff notes
     (deviations, open issues, key files).
7. After phase 09, present the demo results and the acceptance report to
   the user and **stop**. Do not start any later product work.

### Commit identity

`QM_GIT_AUTHOR` is not set in this environment (it may be set to
override). Commit with:

```
git commit --author="Claude Code agent (for Michel Albert) <michel@albert.lu>"
```

Do not touch the committer. End commit messages with the attribution
trailer lines required by the session (Co-Authored-By / Claude-Session)
when the harness provides them.

## Sub-agent rules

- Work only within your task's scope. Do not modify files owned by other
  phases unless the task says so; if you must, report it.
- Follow `DECISIONS.md`. If it is wrong or ambiguous, choose the smallest
  safe assumption, implement it, and report it as a deviation. Do not
  add features, configuration, or dependencies not required by Phase 1.
- Follow quartermaster kit rules (uv only, `create_app` factory,
  routers → services → storage layering, pydantic-settings with
  `ADRIANO_` prefix, Alembic owns schema, docstrings on public symbols,
  test docstrings start with "Ensure …", 80-character lines, Vue
  `<script setup lang="ts">`, no Pinia, fetch-based `api/index.ts`).
- Run the relevant `task` commands (see `Taskfile.yml`) before you
  finish. The dev database is ephemeral: `task db:up` first.
- Do not commit. The coordinator commits.
- Do not mark anything in `STATUS.md`; report to the coordinator.
