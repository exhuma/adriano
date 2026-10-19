---
title: Require trace-id propagation across service boundaries
uuid: 34bf60bb-23d5-4ab7-9b5a-3a7dd41cbeb3
decision-date: 2025-08-01
kind: decision
updates: [c41996ae-e20a-469c-96f9-cb08901b6c7f]
---
# Require trace-id propagation across service boundaries

## Context

The shared logging format defined a `trace_id` field, but did not
require services to propagate it across outbound calls.

## Decision

Every service must propagate the `trace_id` header on outbound
calls, and fall back to generating a new one only at a true system
boundary.

## Consequences

`updates` points from this newer decision to the earlier decision it
updates ("Adopt a shared structured logging format"); the detail
page shows both directions.
