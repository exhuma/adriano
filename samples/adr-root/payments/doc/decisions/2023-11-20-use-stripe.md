---
uuid: febec6b3-ba78-4963-a32f-5420f0f3c69b
decision-date: 2023-11-20
signed-off-by: [carol@example.com]
---
# Use Stripe for card payment processing

We will use Stripe as the card payment processor for all new
payment flows.

## Context

The previous processor's integration required custom PCI scope work
that Stripe's hosted elements avoid.

## Decision

Adopt Stripe as the sole card payment processor for new flows.

## Consequences

Existing integrations with the previous processor are migrated
incrementally. This is a legacy-format record (`uuid`,
`decision-date`, `signed-off-by` only); the sign-off is historical
and unverified.
