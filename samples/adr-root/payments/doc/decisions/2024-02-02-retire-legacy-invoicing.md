---
uuid: ac6890dc-99c4-48f6-a856-d9e931d281cd
decision-date: 2024-02-02
signed-off-by: [carol@example.com, dave@example.com]
deprecates: febec6b3-ba78-4963-a32f-5420f0f3c69b
---
# Retire the legacy invoicing processor integration

## Context

The legacy invoicing processor integration duplicates logic now
covered by the Stripe decision.

## Decision

Retire the legacy invoicing processor integration; new invoices use
the Stripe-backed flow exclusively.

## Consequences

This legacy record uses `deprecates` (not the current `obsoletes`
field) to point at the decision it replaces. The catalog accepts
`deprecates` as a legacy alias of `obsoletes` and reports it as such
(`legacy_alias` warning) so maintainers are not forced to rewrite
existing files.
