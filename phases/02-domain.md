# Phase 02 — Domain core (pure logic)

## Goal

Pure, I/O-free domain modules for hashing, record parsing/validation,
relationships, and approval-state evaluation, fully unit tested.

## Prerequisites

- Phase 01 `done`.

## Context to read

- `phases/DECISIONS.md`: "Record schema", "Canonical content hash",
  "Approval semantics".
- `SPEC.md`: "Legacy ADR file compatibility", "Record schema and
  lifecycle relationships", "Independent approval and sign-off
  workflow".

## Tasks

### Task 1 — Domain modules + tests (model: opus)

Create `backend/app/domain/` with no imports of FastAPI, SQLAlchemy,
httpx, or filesystem APIs.

- `hashing.py`: `canonicalize(raw: bytes) -> str` and
  `content_digest(raw: bytes) -> Digest` (frozen dataclass with
  `algorithm`, `hex`, `__str__` -> `sha256-v1:<hex>`); raw fallback
  `sha256-raw-v1` for undecodable bytes; constant `HASH_VERSION`.
- `records.py`:
  - `is_adr_filename(name) -> bool` with the legacy regex.
  - `parse_record(raw: bytes, *, filename: str) -> ParsedRecord`:
    never raises for content problems. Splits `---` frontmatter, parses
    YAML with `yaml.safe_load`, validates known fields (see
    DECISIONS.md), collects `Issue(severity, code, message)` with
    concise actionable messages (e.g. "`decision-date` must be
    YYYY-MM-DD; got '24/12/2024'").
  - Title derivation: `title` -> first Markdown H1 -> humanised filename
    slug; record `title_source`.
  - Date: `decision-date` or `None`; filename date exposed separately as
    `inferred_date` with a flag; never substituted silently.
  - `kind` default `decision`; `deprecates` mapped into `obsoletes` with
    a `legacy_alias` warning; `signed-off-by` exposed as
    `legacy_signoff: list[str]` with an informational `legacy_signoff`
    issue; `corrects` only valid on `erratum`.
  - Output includes the Markdown body, normalized metadata, outbound
    links `{updates: [...], obsoletes: [...], corrects: uuid|None}`,
    `adr_uuid` (UUID or None).
  - `record_key(adr_uuid, source_id, project, path) -> str`.
- `relationships.py`: given a set of record summaries (key, uuid,
  identity, links), compute for one record: resolved outbound links
  (target found / `missing_target`), inbound links (`updated_by`,
  `obsoleted_by`), errata (reverse `corrects`), derived display status
  (`obsoleted`, `updated`, `active`), and `duplicate_uuid` detection
  across identities. Links resolve by UUID; prefer same project, then
  same registration, then global, and report ambiguity.
- `approval.py`: `Policy` value type (+ `PolicyStatus` for
  missing/invalid), `DecisionEventView`, and
  `evaluate(policy, identity_events, current_digest, approvable: bool)
  -> ApprovalState` with the six states and `needs_approval`, plus
  `last_decided(identity_events)` for the diff default, and
  `is_eligible(policy, issuer, subject, roles) -> bool`.
- Tests in `backend/tests/domain/` (Arrange-Act-Assert, "Ensure …"
  docstrings), including:
  - identical canonical content -> same digest regardless of CRLF/BOM;
    any content edit -> different digest; filename/path not an input;
  - legacy file with `uuid`, `decision-date`, `signed-off-by`,
    `deprecates` parses with expected warnings;
  - malformed YAML, bad UUID, bad date, missing UUID, unknown field each
    yield the right issue and never raise;
  - title fallbacks; inferred date flagged;
  - all six approval states incl. changed-since-acceptance and
    rejected-for-current-hash; missing policy;
  - eligibility by user and by role; read role not eligible.
  - Use property-based testing only if `hypothesis` is cheap to add;
    otherwise parametrized examples.

## Acceptance criteria touched

14, 15, 17, 18, 23 (logic level), 19 (state logic).

## Verification (coordinator)

```
task lint
task test
```

## Definition of done

Green checks; domain package has no forbidden imports (coordinator
greps for `fastapi|sqlalchemy|httpx|open(` in `app/domain`).
