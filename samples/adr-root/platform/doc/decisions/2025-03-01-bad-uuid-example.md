---
title: Record with an invalid UUID
uuid: not-a-valid-uuid
decision-date: 2025-03-01
---
# Record with an invalid UUID

This record's `uuid` field is not a syntactically valid UUID. It is
stored anyway, keyed by its stable source location
(`platform/doc/decisions/2025-03-01-bad-uuid-example.md`) instead of
a UUID, reported with a `bad_uuid` error, and its UUID-based
relationships (`updates`/`obsoletes`/`corrects`) are disabled. It
cannot be approved until the UUID is fixed.
