---
title: Adopt a shared event bus for cross-team notifications
uuid: 6b08e79f-d1a4-42c4-b754-a409c67d4347
decision-date: 2025-06-01
---
# Adopt a shared event bus for cross-team notifications

## Decision

Adopt a shared event bus (topic-based pub/sub) so teams can publish
domain events without each consumer polling the source team's API.

## Note

This record's UUID
(`6b08e79f-d1a4-42c4-b754-a409c67d4347`) is **intentionally reused**
by a record in the `payments` project
(`payments/doc/decisions/2025-07-01-duplicate-uuid-payments.md`), to
demonstrate the `duplicate_uuid` validation issue across two
different project identities. Both records stay browseable; the
duplicate is reported as a warning (two different projects are two
different logical identities, so this is not treated as an error the
way two published paths of the *same* identity would be), and
approval/promotion never crosses projects.
