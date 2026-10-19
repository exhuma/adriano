---
title: Adopt a shared structured logging format
uuid: c41996ae-e20a-469c-96f9-cb08901b6c7f
decision-date: 2024-05-05
kind: decision
---
# Adopt a shared structured logging format

## Context

Each team logs in a slightly different JSON shape, which makes
cross-team log correlation hard.

## Decision

All services log structured JSON lines with a shared minimal set of
fields: `timestamp`, `level`, `service`, `trace_id`, `message`.

## Consequences

This is a cross-project decision owned by the `central` project; it
applies to every project in this catalog, not just one.
