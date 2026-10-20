# Schema examples

These are pointers into `samples/adr-root/`, not copies: duplicating
the files here would let the two drift out of sync. Each line names
the example and the question it answers; see `docs/schema.md` for the
full field reference.

- Legacy file (`uuid`, `decision-date`, `signed-off-by` only):
  `samples/adr-root/platform/doc/decisions/2024-01-10-use-postgresql.md`
- Legacy file using `deprecates` (legacy alias of `obsoletes`):
  `samples/adr-root/payments/doc/decisions/2024-02-02-retire-legacy-invoicing.md`
- Current-schema file (`title`, `kind`, `uuid`), no relationships:
  `samples/adr-root/payments/doc/decisions/2024-09-09-adopt-event-sourcing.md`
- `obsoletes` (replacing record points at the one it replaces):
  `samples/adr-root/platform/doc/decisions/2025-02-20-add-rest-gateway-for-grpc-services.md`
- `updates` (newer record points at the earlier one it updates):
  `samples/adr-root/central/doc/decisions/2025-08-01-add-trace-id-propagation.md`
- Erratum (`erratum-for`, `type: technical`, "Original text" /
  "Corrected text" / "Notes"):
  `samples/adr-root/platform/doc/decisions/errata/2025-05-01-grpc-adoption-erratum.md`
- Editorial erratum (`type: editorial`):
  `samples/adr-root/payments/doc/decisions/errata/2023-12-04-stripe-wording-fix.md`
- Erratum candidate pushed against a published decision (CI push demo):
  `samples/candidates/2026-02-01-erratum-ledger-snapshot-cadence.md`
- Invalid YAML frontmatter (`bad_yaml`):
  `samples/adr-root/platform/doc/decisions/2025-01-05-broken-yaml-frontmatter.md`
- Invalid UUID (`bad_uuid`, falls back to source-location identity):
  `samples/adr-root/platform/doc/decisions/2025-03-01-bad-uuid-example.md`
- Broken link (`missing_target`):
  `samples/adr-root/platform/doc/decisions/2025-04-10-broken-link-example.md`
- Duplicate UUID across two projects (`duplicate_uuid`, a warning):
  `samples/adr-root/platform/doc/decisions/2025-06-01-shared-event-bus.md`
  and
  `samples/adr-root/payments/doc/decisions/2025-07-01-duplicate-uuid-payments.md`
- Nested subfolder discovery:
  `samples/adr-root/platform/doc/decisions/2024/2024-11-01-use-feature-flags.md`
- Non-ADR file, correctly ignored by discovery:
  `samples/adr-root/central/doc/decisions/README.md`
- Candidate push bodies (CI push demo):
  `samples/candidates/` and `samples/push-candidate.sh`
