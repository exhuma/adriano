---
uuid: 113c10a5-faad-4877-bd44-9f9ff69dc2eb
decision-date: 2024-01-10
signed-off-by: [alice@example.com, bob@example.com]
---
# Use PostgreSQL for the platform database

We will use PostgreSQL as the primary relational database for the
platform project.

## Context

The team previously evaluated MySQL and PostgreSQL. We need strong
support for JSONB columns, full-text search, and advisory locks for
coordinating background workers across replicas.

## Decision

Adopt PostgreSQL 18 as the only supported relational database engine
for new platform services.

## Consequences

Operators provision PostgreSQL instead of MySQL for new services.
Existing MySQL databases are migrated on a case-by-case basis.

This is a legacy-format record: it predates the `title`/`kind` schema
and uses the old `uuid`, `decision-date`, and `signed-off-by` fields
only. `signed-off-by` is a historical artifact of the previous
process and is shown as "Legacy sign-off (unverified)"; it is not a
catalog approval.
