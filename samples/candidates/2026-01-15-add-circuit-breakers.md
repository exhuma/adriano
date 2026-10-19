---
title: Add circuit breakers to outbound service calls
uuid: 3f5e1b69-f3bf-4fb4-b173-ccfa92d8baab
decision-date: 2026-01-15
kind: decision
---
# Add circuit breakers to outbound service calls

## Context

A single slow downstream dependency has repeatedly degraded unrelated
request paths.

## Decision

Wrap outbound calls to other services in a circuit breaker with a
sane default timeout and failure threshold.

## Demo note

This candidate is left pending, to populate the "Needs approval"
filter alongside the policy-missing and rejected examples.
