# Phase 07 — Candidate intake, decisions, diff (approval slice)

## Goal

CI can submit candidates through authenticated PUT/POST. Eligible
reviewers can accept or reject the exact content hash. Readers see
approval state, history, divergence, diffs, and a "Needs approval"
filter.

## Prerequisites

- Phases 01–06 `done`.

## Context to read

- `phases/DECISIONS.md`: "Approval semantics", "HTTP API",
  "Persistence".
- `SPEC.md`: "Independent approval and sign-off workflow", "Source
  registrations and intake" (push), criteria 3, 7, 12, 13, 16–22.

## Tasks

### Task 1 — Intake, decisions, diff backend (model: opus)

- `services/intake.py` + `routers/candidates.py`: `PUT` and `POST
  /api/v1/candidates` exactly as in DECISIONS.md. Push-token auth is a
  separate dependency (not OIDC), scoped to the registration and to
  candidate-write only (a push token must not read the catalog).
  `delivery_id` dedup returns the earlier result. Reuse
  `services/ingest.py`. Record an `intake_run` for every request
  (success, 4xx validation, auth failure without leaking token).
  Response: record id, digest, issues, catalog URL path, created/updated.
- `services/decisions.py` + `routers/decisions.py`:
  `POST /api/v1/records/{id}/decisions` — policy present, caller
  eligible, record approvable, not self-approval, then append event with
  policy id/version and provenance; 409 when already decided for that
  hash. Clear error bodies: `{code, message, hint}`.
- Detail payload: decision history for the identity (all digests,
  marked current/other), approval state, policy summary, divergence
  info, competing candidates, `can_decide` + reason for the caller.
- `needs_approval=true` filter on `/records` (SQL predicate from phase
  03).
- `services/diff.py` + `GET /api/v1/records/{id}/diff` (difflib unified
  diff of stored snapshots; default base per DECISIONS.md).
- Tests (criteria-driven): PUT idempotent, POST 409, UUID mismatch 422,
  out-of-scope project 403, wrong registration token 403, published ref
  refused, candidate never overwrites published, delivery_id dedup,
  accept/reject by eligible user/role, non-eligible 403, self-approval
  403, decided twice 409, **identical content on published ref after
  poll shows accepted with same history** (filesystem tree in
  `tmp_path`), edited content -> `changed_since_acceptance` with old
  history retained, diff between accepted snapshot and current,
  needs-approval returns pending/rejected/changed/policy_missing and
  excludes accepted/not_required, history survives a new app instance.

### Task 2 — Approval UI (model: sonnet)

- Candidate vs published distinction everywhere (chip + text, ref
  provenance); accepted candidates labelled "Accepted — candidate" and
  discoverable via the state filter.
- "Needs approval" switch on the search page (URL param).
- Record page approval card: state with explanation (distinguish
  "policy not configured — contact an operator" from "awaiting
  review"), policy summary, history table (reviewer, timestamp, action,
  comment, digest short + copy), Accept/Reject dialog with optional
  comment, confirmation of the exact digest, success/error feedback,
  disabled controls always with a visible reason.
- Divergence and competing-candidate banners with links.
- Diff panel: base/target digests, refs, freshness; accessible
  (`<pre>` with +/- prefixes, not colour alone); "no prior revision"
  empty state.
- vitest for approval-state presentation helpers.

## Acceptance criteria touched

3, 7, 12, 13, 16, 17, 18, 19, 20, 22.

## Verification (coordinator)

```
task lint && task test && task build
```

Playwright: push a candidate with curl, sign in as reviewer, accept,
see "Accepted — candidate"; copy identical file into the polled tree,
poll, see "Accepted — published"; edit and poll, see "changed since
acceptance" + diff; needs-approval filter shows it.

## Definition of done

Green checks; the full governance loop works end to end.
