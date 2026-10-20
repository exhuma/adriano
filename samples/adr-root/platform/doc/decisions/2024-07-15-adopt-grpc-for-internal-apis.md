---
title: Adopt gRPC for internal APIs
uuid: 70cba06c-46f1-4000-a088-0fe467a12a2c
decision-date: 2024-07-15
---
# Adopt gRPC for internal APIs

## Context

Internal service-to-service calls currently use ad hoc REST/JSON. As
the number of internal services grows, we want a typed contract and
lower serialization overhead.

## Decision

New internal service-to-service APIs are defined with Protocol
Buffers and served over gRPC. Public-facing APIs are unaffected and
stay REST/JSON.

## Consequences

Teams adopt a shared `.proto` repository and generated client/server
stubs. This record uses the current schema (`title`, `uuid`); it has
no `updates`/`obsoletes` relationships.
