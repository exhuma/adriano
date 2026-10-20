---
title: Adopt event sourcing for the ledger service
uuid: 487f840d-09ea-4ed6-8057-5bb673c198c6
decision-date: 2024-09-09
kind: decision
---
# Adopt event sourcing for the ledger service

## Decision

The ledger service stores an append-only event log as its system of
record; current balances are a derived projection.

## Consequences

Replays and audits read the event log directly. This record keeps an
obsolete `kind: decision` line on purpose: `kind` is no longer part
of the schema (a document is an erratum because it has
`erratum-for`, not because of `kind`), so this field now yields an
`obsolete_kind_field` warning instead of being read. The record is
otherwise a normal, valid decision.
