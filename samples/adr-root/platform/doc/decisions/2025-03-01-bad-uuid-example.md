---
title: Record with an invalid UUID
uuid: not-a-valid-uuid
decision-date: 2025-03-01
---
# Record with an invalid UUID

This file's `uuid` field is not a syntactically valid UUID. Without
a valid UUID the document has no identity, so it is not indexed. It
appears in the "Not indexed" list with the reason `bad_uuid` and its
content, and the entry disappears once the UUID is fixed and the file
is polled again.
