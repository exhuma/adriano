# Approval workflow

Audience: reviewers, operators, and developers integrating CI push.
Approval policy and decision history live in the application
database, never in the ADR Markdown files themselves -- see
`docs/schema.md` for the document schema and `docs/hashing.md` for
the content digest that approval is bound to.

## Policy configuration

One global policy, configured in `catalog.yaml`'s `approval_policy`
(see `catalog.example.yaml`):

```yaml
approval_policy:
  id: global
  version: 1
  required: true
  reviewers:
    users: ["https://idp.example.com|subject-123"]  # issuer|subject
    roles: [adr-reviewer]
  allow_self_approval: false
```

- `required: false` means the catalog does not demand approval at
  all (state `not_required` everywhere).
- `reviewers.users` lists specific `issuer|subject` pairs (matched
  against the verified token, not a display name or email).
  `reviewers.roles` lists IdP roles (from the claim named by
  `ADRIANO_OIDC_ROLES_CLAIM`) that are also eligible.
- A reviewer's **read** permission (`rbac`) is independent of being a
  reviewer: granting `read` never grants review rights, and being a
  reviewer does not by itself grant `read`/`operate`.
- A missing or invalid `approval_policy` does **not** stop the
  application from starting. It produces the `policy_missing` state
  everywhere, reported in `/healthz`, `GET /api/v1/sources`, and the
  UI, and **all decisions are refused** until it is fixed.

## States

Approval state is a pure function of the current digest's decision
history (`backend/app/domain/approval.py`), evaluated per logical
identity (`source_id`, `project`, `record_key` -- the ADR UUID, or the
source-location fallback key described in `docs/schema.md`).

| State | Condition | In "Needs approval"? |
|---|---|---|
| `policy_missing` | Policy absent or invalid. | yes |
| `not_required` | Policy `required: false`. | no |
| `accepted` | An `accepted` decision exists for this identity *and this exact digest*. | no |
| `rejected` | A `rejected` decision exists for this identity and this digest. | yes |
| `changed_since_acceptance` | An `accepted` decision exists for this identity, but for a *different* digest than the current one. | yes |
| `pending` | None of the above. | yes |

A record with an error-severity identity problem (no valid UUID, or
`bad_encoding`) always shows `pending` with the reason, and cannot be
decided until the problem is fixed.

## Candidate vs. published

- A **candidate** is content on a non-default branch/ref, submitted
  by poll or by CI push. A **published** record is the latest
  successfully polled content on the registration's configured
  published/default ref.
- Approval evaluates the *stored revision*, never a live source read.
  For published records, that means the latest successfully polled
  content -- freshness (next to the state) tells the reader whether
  that is actually current; see "Freshness and stale polls" below.

## Acceptance before publication

A reviewer may accept a candidate while it is still on a feature
branch. The UI shows "Accepted -- candidate" with its branch/ref
provenance. This is intentional: Phase 1 lets implementation proceed
from an accepted candidate before it reaches the default branch.

## Promotion

Decisions are keyed by **(identity, digest)**, not by which row they
were made against. When polling later finds the *same digest* on the
published ref, the published row's state becomes `accepted`
("Accepted -- published") automatically, with the full decision
history intact -- nothing is copied, re-decided, or re-approved. See
`docs/hashing.md` test vector 2 for a real, reproduced example
(`samples/candidates/2026-01-05-use-redis-for-caching.md`).

## Divergence

If the published digest for an identity differs from an already
accepted candidate's digest, **both rows stay**: the published row
shows `changed_since_acceptance` (or `pending`, if nothing was ever
accepted for it) and links to the accepted candidate. Acceptance is
never silently transferred across digests; the new content needs its
own decision.

## Competing candidates

Several candidates of one identity can exist at once on different
refs (e.g. two proposals pushed from different feature branches).
Each is a separate row with its own independent approval state. The
detail page lists all of them with a warning. Deciding one candidate
never affects another candidate's digest or state.

## One decision per content hash; append-only

- `UNIQUE (source_id, project, record_key, digest)` on the decision
  table: at most one formal decision exists per content hash per
  identity. A second `POST .../decisions` for an already-decided
  digest is refused with `409 already_decided`.
- Decision rows are never updated or deleted (a database trigger
  enforces this). A rejection applies only to its exact digest;
  changed content gets its own, independent decision state.

## Self-approval and its limits

With `allow_self_approval: false` (the Phase 1 default), a reviewer
is refused if their verified email equals the record's `author`.
`author` is only known for **CI-pushed candidates** that supplied it,
or for GitLab-polled content (commit author, when available).
**Filesystem-polled records have no author** (the adapter has no
concept of one), so this check cannot block self-approval of a
filesystem-sourced record -- a known, documented limitation of the
`filesystem` source type, not a security promise of the policy
itself.

## What reviewers see

The record detail page's approval card shows: the current state and
policy summary; full decision history (actor, action, comment,
timestamp, policy id/version); a divergence banner when applicable;
competing candidates; and, for an eligible reviewer on a decidable
record, an Accept/Reject dialog requiring a comment is optional but
supported. `GET /api/v1/me` reports whether the signed-in principal
is an eligible reviewer and why not, when they are not.

## CI workflow

A CI pipeline pushes a candidate (never a published record -- push
intake can only create/replace candidates, see `docs/api-migration.md`
is not relevant here, see `docs/operator.md` "CI push example"); a
human reviewer then accepts or rejects it through the UI or the API.
See `samples/push-candidate.sh` for a working example and
`docs/operator.md` for the GitLab CI job snippet.

## Freshness and stale polls

When a registration's last successful poll is older than
`ADRIANO_STALE_AFTER_MINUTES`, or its last poll failed or partially
failed, the UI shows a stale/failed banner next to the published
state and never claims that the indexed revision is the current
published source content (acceptance criterion 21). Approval state
for the published row is still evaluated normally against whatever
was last successfully indexed.
