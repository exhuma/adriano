# ADR record schema

Audience: developers writing or reviewing ADR Markdown files. For the
durable approval/acceptance model (not authored in these files), see
`docs/approval.md`.

## File location and discovery

A record is a Markdown file under a registration's configured ADR path
(default `doc/decisions/`), discovered recursively. Only filenames
matching this pattern are indexed:

```text
^\d{4}-\d{2}-\d{2}-(.*)\.md$
```

For example `doc/decisions/2024-12-24-use-postgresql.md`. A file that
does not match (for example a plain `README.md` sitting next to real
ADRs) is silently ignored; see
`samples/adr-root/central/doc/decisions/README.md`.

## Frontmatter fields

```yaml
---
uuid: 0b0c2f4e-1111-4a11-9a11-111111111111
title: Use PostgreSQL
decision-date: 2024-12-24
kind: decision
updates: []
obsoletes: []
corrects: null
---
Markdown body
```

| Field | Required | Meaning |
|---|---|---|
| `uuid` | yes | Stable record identity. |
| `title` | no | Display title; falls back to the first H1, then the humanised filename. |
| `decision-date` | no | ISO `YYYY-MM-DD`. Never silently replaced by the filename date. |
| `kind` | no | `decision` (default) or `erratum`. |
| `updates` | no | UUIDs of earlier decisions this one updates. |
| `obsoletes` | no | UUIDs of decisions this one replaces. |
| `corrects` | erratum only | UUID of the decision this erratum corrects. |

## Legacy compatibility fields

These predate the current schema and are still fully supported so
existing files never need to be rewritten:

| Field | Current equivalent | Behaviour |
|---|---|---|
| `uuid`, `decision-date` | same names | No change; these were never renamed. |
| `signed-off-by` | none (approval moved to the backend) | Parsed and shown as "Legacy sign-off (unverified)". It never counts as an authenticated approval -- see `docs/approval.md`. |
| `deprecates` | `obsoletes` | Merged into `obsoletes`, reported as `legacy_alias` (a warning, not an error). |

See `samples/adr-root/platform/doc/decisions/2024-01-10-use-postgresql.md`
(legacy `uuid`/`decision-date`/`signed-off-by`) and
`samples/adr-root/payments/doc/decisions/2024-02-02-retire-legacy-invoicing.md`
(legacy `deprecates`).

## Title and date fallbacks

- **Title:** explicit `title` -> first Markdown H1 (outside code
  fences) -> humanised filename (e.g. `use-postgresql` ->
  "Use postgresql"). The chosen source is recorded
  (`frontmatter`/`h1`/`filename`) and shown in the UI, never hidden.
- **Decision date:** explicit `decision-date` only. A date parsed from
  the filename prefix is shown separately, labelled "inferred from
  filename"; it is never substituted for a missing authored date
  without that label.

## Relationship semantics

- **`updates`** points from the **newer** decision to the **earlier**
  decision it updates.
- **`obsoletes`** points from the **replacing** decision to the
  decision it **replaces**.
- **Errata** are separate records (`kind: erratum`) with their own
  UUID, linked to the decision they correct via `corrects`. The
  reverse "errata for this decision" listing on the corrected record
  is *derived* by the catalog at read time; it is never authored on
  the corrected record itself, so there is only one source of truth.

Examples: `samples/adr-root/platform/doc/decisions/2025-02-20-add-rest-gateway-for-grpc-services.md`
(`obsoletes`), `samples/adr-root/central/doc/decisions/2025-08-01-add-trace-id-propagation.md`
(`updates`), `samples/adr-root/platform/doc/decisions/2025-05-01-erratum-for-grpc-adoption.md`
(erratum + `corrects`).

Display status (e.g. "Obsoleted by ...", "Updated by ...") is always
derived from these links at read time. There is no separate
authored/stored status field, and Phase 1 deliberately has no graph
view -- only direct inbound/outbound links on the detail page.

## Identity without a valid UUID

A record without a syntactically valid `uuid` is still stored and
browseable, keyed by its stable source location
(`source_id/project/path`) instead of a UUID. Its UUID-based
relationships (`updates`/`obsoletes`/`corrects`) are disabled, and it
cannot be approved until the UUID is fixed. No UUID is invented on its
behalf -- a generated UUID could be mistaken for a maintainer-authored
decision ID. Example:
`samples/adr-root/platform/doc/decisions/2025-03-01-bad-uuid-example.md`.

## Validation issue codes

Every problem becomes a `{severity, code, message}` issue stored on
the record. A problem in one record never affects any other record.

| Code | Severity | Meaning | What to do |
|---|---|---|---|
| `bad_yaml` | error | Frontmatter is not valid YAML. | Fix the YAML syntax; the record is stored under a fallback (raw-bytes) digest and cannot be approved until fixed. |
| `missing_frontmatter` | error | No `---`-delimited frontmatter block found. | Add a frontmatter block with at least `uuid`. |
| `missing_uuid` | error | `uuid` field absent. | Add a `uuid`. |
| `bad_uuid` | error | `uuid` is not a valid UUID. | Fix the UUID; see "Identity without a valid UUID" above. |
| `bad_date` | error | `decision-date` is not a valid ISO date. | Fix the date or remove the field. |
| `missing_date` | warning | No `decision-date`. | Add one, or rely on the filename-inferred date (clearly labelled). |
| `unknown_field` | warning | A frontmatter key the catalog does not understand. | Remove it or check for a typo. |
| `bad_field_type` | error | A known field has the wrong shape (e.g. `kind` is not `decision`/`erratum`). | Fix the value. |
| `duplicate_uuid` | error (same identity) / warning (different identity) | Two published paths of the same identity share a UUID, or two different identities (projects) do. | Pick one canonical UUID per decision; see `samples/adr-root/platform/doc/decisions/2025-06-01-shared-event-bus.md`. |
| `missing_target` | warning | An `updates`/`obsoletes`/`corrects` UUID does not match any record. | Fix the target UUID, or leave it if the target was intentionally removed. |
| `ambiguous_target` | warning | A relationship target resolves to more than one candidate revision. | Usually resolves itself once one candidate is accepted or rejected. |
| `legacy_alias` | warning | `deprecates` used instead of `obsoletes`. | No action required; informational. |
| `legacy_signoff` | warning | `signed-off-by` present. | No action required; shown as "Legacy sign-off (unverified)", never an approval. |
| `corrects_on_non_erratum` | error | `corrects` set on a record whose `kind` is not `erratum`. | Set `kind: erratum`, or remove `corrects`. |
| `erratum_without_target` | error | `kind: erratum` with no (valid) `corrects`. | Add a valid `corrects` UUID. |
| `bad_encoding` | error | File bytes are not valid UTF-8. | Re-save the file as UTF-8. The record is stored under the raw-bytes digest (`sha256-raw-v1:...`) and cannot be approved until fixed. |

See `docs/examples/README.md` for a worked example of each issue code
using the bundled sample files.
