---
title: "Unterminated string makes this YAML invalid
uuid: 9c6e5e2c-0000-4000-8000-000000000001
decision-date: 2025-01-05
---
# Broken YAML frontmatter

This file intentionally has invalid YAML frontmatter (an unterminated
quoted string on the `title` line, with no closing `"`). The
frontmatter cannot be read, so the document is not indexed. It
appears in the "Not indexed" list with the reason `bad_yaml`, and
every other record stays browseable.
