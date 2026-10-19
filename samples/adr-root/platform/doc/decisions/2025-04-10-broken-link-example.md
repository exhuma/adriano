---
title: Record with a broken outbound link
uuid: 5e2a1a0a-7a3a-4a0a-9a0a-111111111111
decision-date: 2025-04-10
kind: decision
obsoletes: [2f6c1926-939e-44c1-a8f5-1c9c523fc849]
---
# Record with a broken outbound link

## Decision

This record's `obsoletes` field points at a UUID
(`2f6c1926-939e-44c1-a8f5-1c9c523fc849`) that does not match any
record in the catalog. It demonstrates the `missing_target`
validation issue: the record itself stays fully browseable, and only
the broken relationship is flagged.
