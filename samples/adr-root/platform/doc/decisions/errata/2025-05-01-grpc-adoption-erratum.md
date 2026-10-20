---
uuid: 103eda7f-dafa-4395-a286-db1488b67d49
erratum-for: 70cba06c-46f1-4000-a088-0fe467a12a2c
type: technical
section: Decision
reported-by: priya.nair@example.com
date: 2025-05-01
---
## Original text

New internal service-to-service APIs are defined with Protocol
Buffers and served over gRPC. Public-facing APIs are unaffected and
stay REST/JSON.

## Corrected text

New internal service-to-service APIs are defined with Protocol
Buffers and served over gRPC; **all** new internal clients, not only
new servers, must use the generated stubs. Public-facing APIs are
unaffected and stay REST/JSON.

## Notes

No new decision is required; this erratum only clarifies the
original record's scope. `erratum-for` links this file to the
decision it corrects (uuid
`70cba06c-46f1-4000-a088-0fe467a12a2c`, "Adopt gRPC for internal
APIs"); the catalog derives the reverse "errata for this decision"
listing on the corrected record automatically, it is not authored
there.
