---
uuid: 201eeb83-8117-43c2-b429-aba67ee26f90
erratum-for: 487f840d-09ea-4ed6-8057-5bb673c198c6
type: technical
section: Consequences
reported-by: morgan.lee@example.com
date: 2026-02-01
---
## Corrected text

Replays and audits read the event log directly. For a ledger whose
event log exceeds 50,000 events, a snapshot of the derived
projection is taken every 24 hours so replay time stays bounded; the
append-only event log stays the system of record.

## Notes

A production replay of a high-volume ledger took over 40 minutes
with no snapshot in place; this clarifies the consequence the
original record omitted. No "Original text" section is included
because this is a pure addition, not a correction of existing
wording.

Demo note: this file is pushed as an **erratum candidate** (see
`samples/push-candidate.sh`) against the already-published "Adopt
event sourcing for the ledger service" decision
(`samples/adr-root/payments/doc/decisions/2024-09-09-adopt-event-sourcing.md`).
A reviewer verifies it while still a candidate, demonstrating the
erratum report -> verify workflow described in
`phases/10-ui-errata.md`; see `docs/demo/README.md` section 14 for
the resulting UI wording.
