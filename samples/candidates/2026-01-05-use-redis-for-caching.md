---
title: Use Redis for application-level caching
uuid: b87a5fc5-a48f-49cb-a029-ac1f7c56c717
decision-date: 2026-01-05
kind: decision
---
# Use Redis for application-level caching

## Context

Several services independently added ad hoc in-process caches with
no shared eviction policy.

## Decision

Adopt Redis as the shared application-level cache for new caching
needs; in-process caches stay only for microsecond-latency lookups.

## Consequences

Services gain a dependency on the shared Redis cluster.

## Demo note

This file is pushed as a **candidate** on a feature branch (see
`samples/push-candidate.sh`), accepted by a reviewer while still a
candidate ("Accepted — candidate"), and later copied byte-for-byte
into `samples/adr-root/platform/doc/decisions/`. Because the content
is identical, the next poll promotes it to "Accepted — published"
with the same digest and the same acceptance history, demonstrating
identical-content promotion (acceptance criterion 13).
