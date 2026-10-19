---
title: Add a REST gateway in front of gRPC services
uuid: 1790fef2-54d8-4191-84a1-3b7104c4940c
decision-date: 2025-02-20
kind: decision
obsoletes: [70cba06c-46f1-4000-a088-0fe467a12a2c]
---
# Add a REST gateway in front of gRPC services

## Context

External partners occasionally need to call internal services that
moved to gRPC-only, but cannot adopt a gRPC client.

## Decision

Internal services exposed to partners run a generated REST/JSON
gateway (grpc-gateway) alongside their gRPC listener, replacing the
gRPC-only approach from "Adopt gRPC for internal APIs".

## Consequences

Services that need external exposure carry a small amount of extra
generated code. `obsoletes` points from this (the replacing) record
to the earlier decision it replaces.
