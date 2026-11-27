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

This file deliberately carries the UUID of
`payments/doc/decisions/2025-07-01-duplicate-uuid-payments.md`
(`6b08e79f-d1a4-42c4-b754-a409c67d4347`), to demonstrate the
`duplicate_uuid` reason of the "Not indexed" list.

An ADR is identified by its UUID alone, across all projects. The
payments file is indexed first (projects are applied in name order on
the first poll), so it holds the UUID and this file is not indexed. It
appears in the "Not indexed" list with the holder named. Giving this
file its own UUID makes the next poll index it and clear the entry.
