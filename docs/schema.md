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
updates: []
obsoletes: []
---
Markdown body
```

| Field | Required | Meaning |
|---|---|---|
| `uuid` | yes | Stable record identity. |
| `title` | no | Display title; falls back to the first H1, then the humanised filename. |
| `decision-date` | no | ISO `YYYY-MM-DD`. Never silently replaced by the filename date. |
| `updates` | no | UUIDs of earlier decisions this one updates. |
| `obsoletes` | no | UUIDs of decisions this one replaces. |

`kind` and `corrects` are no longer part of this schema -- an erratum
is a separate file format, not a decision field (see "Errata" below):

- `kind: decision` is harmless but obsolete: it is ignored and
  reported as an `obsolete_kind_field` warning. Remove the line; the
  record is otherwise unaffected.
- `kind: erratum` (any case) or any `corrects` key is the retired
  erratum shape and is reported as a `legacy_erratum_format` error. To
  convert: move the file into its own erratum file (see "Errata"
  below), replace `corrects: <uuid>` with `erratum-for: <uuid>`, add
  `type: technical` or `type: editorial`, and reorganise the body into
  a `## Corrected text` section (required), plus `## Original text`
  and `## Notes` if useful.

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
- **Errata** are separate records with their own `uuid` (see "Errata"
  below), linked to the decision they correct via `erratum-for`
  (internally resolved through the same `corrects` link). The reverse
  "errata for this decision" listing on the corrected record is
  *derived* by the catalog at read time; it is never authored on the
  corrected record itself, so there is only one source of truth.

Examples: `samples/adr-root/platform/doc/decisions/2025-02-20-add-rest-gateway-for-grpc-services.md`
(`obsoletes`), `samples/adr-root/central/doc/decisions/2025-08-01-add-trace-id-propagation.md`
(`updates`), `samples/adr-root/platform/doc/decisions/errata/2025-05-01-grpc-adoption-erratum.md`
(erratum + `erratum-for`, quoted in full under "Errata" below).

Display status (e.g. "Obsoleted by ...", "Updated by ...") is always
derived from these links at read time. There is no separate
authored/stored status field, and Phase 1 deliberately has no graph
view -- only direct inbound/outbound links on the detail page.

## Errata

An erratum is a short, RFC-style report about a problem found in an
**existing** decision -- never a new decision, and never a way to
edit the original file. Filing, verifying, or rejecting an erratum
never changes the corrected decision's content hash or approval state;
the decision keeps its own content and history untouched. An erratum
is itself a record with its own identity, content hash, and approval
workflow (see `docs/approval.md` "Errata").

### File location

An erratum is a Markdown file with its own frontmatter, discovered by
the same filename rule as decisions (see "File location and
discovery" above). The recommended location is
`doc/decisions/errata/YYYY-MM-DD-<slug>.md`, alongside but separate
from the decisions it corrects. A document is an erratum because its
frontmatter has `erratum-for`, never because of its path.

### Frontmatter fields

| Field | Required | Meaning |
|---|---|---|
| `uuid` | yes | The erratum's own stable identity (separate from the decision it corrects; used for its own approval and candidates). |
| `erratum-for` | yes | UUID of the decision this erratum corrects. |
| `type` | yes | `technical` or `editorial`. |
| `section` | no | Where in the decision the problem is (free text, e.g. `Consequences`). Also used to build the erratum's fallback title. |
| `reported-by` | no | Free-text name or email of whoever reported it. Informational only -- it is never treated as an identity and is never compared against the signed-in reviewer. |
| `date` | no | ISO `YYYY-MM-DD` report date. |

### Body sections

The body is split on three H2 headings, matched case-insensitively and
tolerating a trailing colon:

| Heading | Required | Meaning |
|---|---|---|
| `## Original text` | no | The exact text as written in the decision. Omit it for a pure addition the decision never mentioned. |
| `## Corrected text` | yes | The replacement wording. Missing or empty yields `erratum_missing_corrected_text`. |
| `## Notes` | no | Rationale or extra context. |

Content before the first heading, or under any other H2 heading, is
kept (never discarded) but filed under notes, with an
`erratum_unknown_section_heading` warning so a misplaced heading is
easy to find and fix. Repeating a heading joins the parts in order,
with an `erratum_duplicate_section` warning.

Only `##` (ATX) headings start a section: a setext heading (`Notes`
underlined with `---`) is ordinary text. A code fence that is never
closed runs to the end of the file, so any heading after it is part of
the code block.

### Example

`samples/adr-root/platform/doc/decisions/errata/2025-05-01-grpc-adoption-erratum.md`:

```markdown
---
uuid: 103eda7f-dafa-4395-a286-db1488b67d49
erratum-for: 70cba06c-46f1-4000-a088-0fe467a12a2c
type: technical
section: Decision
reported-by: priya.nair@example.com
date: 2025-05-01
---
## Original text

New internal service-to-service APIs are defined with Protocol
Buffers and served over gRPC. Public-facing APIs are unaffected and
stay REST/JSON.

## Corrected text

New internal service-to-service APIs are defined with Protocol
Buffers and served over gRPC; **all** new internal clients, not only
new servers, must use the generated stubs. Public-facing APIs are
unaffected and stay REST/JSON.

## Notes

No new decision is required; this erratum only clarifies the
original record's scope. `erratum-for` links this file to the
decision it corrects (uuid `70cba06c-46f1-4000-a088-0fe467a12a2c`,
"Adopt gRPC for internal APIs"); the catalog derives the reverse
"errata for this decision" listing on the corrected record
automatically, it is not authored there.
```

### Attaching an erratum to a decision

`erratum-for` is a UUID reference, resolved by the same rules as
`updates`/`obsoletes` (see "Relationship semantics" above): the
catalog prefers a decision in the **same project of the same
registration**, falling back to the same registration, then to any
registration. If more than one decision at the best-matching tier
shares that UUID, the link is **ambiguous** and attaches to **none**
of them -- the erratum's page shows "erratum for an unknown decision"
rather than guessing. The reverse "errata for this decision" list
shown on the corrected decision's page is always derived this way,
never authored.

### Validation issue codes (errata)

| Code | Severity | Meaning | What to do |
|---|---|---|---|
| `bad_erratum_type` | error | `type` is missing or not `technical`/`editorial`. | Set `type: technical` or `type: editorial`. |
| `erratum_missing_corrected_text` | error | No (non-empty) `## Corrected text` section. | Add one with the replacement wording. |
| `erratum_unknown_section_heading` | warning | Text before the first heading, or under any heading other than `Original text`/`Corrected text`/`Notes`. | Move the text under one of the three recognised headings. |
| `erratum_duplicate_section` | warning | A recognised heading (`Original text`/`Corrected text`/`Notes`) appears more than once; the parts are joined in order. | Use each heading once. |
| `erratum_relationship_ignored` | warning | `updates`/`obsoletes` (or `deprecates`) on an erratum; they are decision relationships and are dropped. | Remove them; record lifecycle changes in a decision. |
| `erratum_target_is_erratum` | warning | `erratum-for` resolves to another erratum (checked when the page is read). The link is shown, but an erratum never lists errata of its own. | Point `erratum-for` at the decision being corrected. |
| `erratum_targets_itself` | error | `erratum-for` is the erratum's own `uuid`. | Set it to the corrected decision's UUID; until then the erratum is not linked. |
| `erratum_without_target` | error | `erratum-for` is missing or not a valid UUID. | Add a valid `erratum-for` UUID; until then the erratum is not linked to any decision. |
| `legacy_erratum_format` | error | `kind: erratum` (any case), or any `corrects` key -- the retired erratum shape. | Convert to this format: `erratum-for` instead of `corrects`, add `type`, and split the body into "Corrected text" (required), plus "Original text"/"Notes" if useful. |

See `docs/examples/README.md` for the bundled examples (a technical
erratum, an editorial erratum, and a pushed erratum candidate).

## Identity without a valid UUID

A record without a syntactically valid `uuid` is still stored and
browseable, keyed by its stable source location
(`source_id/project/path`) instead of a UUID. Its UUID-based
relationships (`updates`/`obsoletes`/`erratum-for`) are disabled, and
it cannot be approved until the UUID is fixed. No UUID is invented on its
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
| `bad_field_type` | error | A known field has the wrong shape (e.g. `updates` is not a list of UUIDs). | Fix the value. |
| `duplicate_uuid` | error (same identity) / warning (different identity) | Two published paths of the same identity share a UUID, or two different identities (projects) do. | Pick one canonical UUID per decision; see `samples/adr-root/platform/doc/decisions/2025-06-01-shared-event-bus.md`. |
| `missing_target` | warning | An `updates`/`obsoletes`/`erratum-for` UUID does not match any record. | Fix the target UUID, or leave it if the target was intentionally removed. |
| `ambiguous_target` | warning | A relationship target resolves to more than one candidate revision. | Usually resolves itself once one candidate is accepted or rejected. |
| `legacy_alias` | warning | `deprecates` used instead of `obsoletes`. | No action required; informational. |
| `legacy_signoff` | warning | `signed-off-by` present. | No action required; shown as "Legacy sign-off (unverified)", never an approval. |
| `obsolete_kind_field` | warning | `kind: decision` is present. | Remove the `kind` line; no other change needed. |
| `legacy_erratum_format` | error | `kind: erratum` (any case), or any `corrects` key -- the retired erratum shape. | Convert to the current erratum format; see "Errata" above. |
| `bad_encoding` | error | File bytes are not valid UTF-8. | Re-save the file as UTF-8. The record is stored under the raw-bytes digest (`sha256-raw-v1:...`) and cannot be approved until fixed. |

Erratum-only codes (`bad_erratum_type`, `erratum_missing_corrected_text`,
`erratum_unknown_section_heading`, `erratum_without_target`,
`erratum_duplicate_section`, `erratum_relationship_ignored`,
`erratum_target_is_erratum`, `erratum_targets_itself`) are listed
in "Errata" above.

See `docs/examples/README.md` for a worked example of each issue code
using the bundled sample files.
