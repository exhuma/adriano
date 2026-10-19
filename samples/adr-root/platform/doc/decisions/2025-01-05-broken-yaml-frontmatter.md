---
title: "Unterminated string makes this YAML invalid
uuid: 9c6e5e2c-0000-4000-8000-000000000001
decision-date: 2025-01-05
---
# Broken YAML frontmatter

This file intentionally has invalid YAML frontmatter (an unterminated
quoted string on the `title` line, with no closing `"`). It is used
to demonstrate that one malformed record does not take down the
whole catalog: it is stored and reported with a `bad_yaml` error, and
every other record stays browseable.
