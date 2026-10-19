---
title: Use a feature-flag service for staged rollouts
uuid: a30833f1-df66-4fbc-afd8-9a10472e0ee1
decision-date: 2024-11-01
kind: decision
---
# Use a feature-flag service for staged rollouts

## Context

Deploys and feature rollouts were previously coupled. We want to
decouple "the code is deployed" from "the feature is on".

## Decision

Adopt a hosted feature-flag service for all staged rollouts and
kill switches.

## Consequences

New risky features are guarded by a flag by default.

This file lives in a nested subfolder (`doc/decisions/2024/`) under
the registration path, demonstrating that ADR discovery is
recursive.
