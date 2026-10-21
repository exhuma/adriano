0001: Keep the first release governance-first
=============================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

Adriano replaces an older ADR viewer that scraped one source on every
request and had no approval workflow.
The new catalog serves several teams and had to be useful within days,
not a full governance platform.

Decision
--------

The first release covers exactly:
config-file source registrations,
polling of published refs and CI push of candidates through one shared
ingest path,
candidate and published states,
one formal accept/reject decision per content hash under a single
global policy,
search and detail pages with three filters
(source/project, candidate/published, needs approval),
basic typed links with legacy ``deprecates`` support,
authentication, RBAC and health reporting.

Explicitly deferred, not to be built without a new scoped decision:
an admin or configuration UI,
webhooks and more source types,
quorum or multi-stage review, notifications and revocation,
graph views, cycle analysis and date or lifecycle facets,
identity-conflict remediation tools,
a tamper-evident audit export,
and LLM features.

Consequences
------------

* Configuration changes need a restart (:doc:`0009-single-config-file`).
* Some edge cases are handled minimally and documented as limits
  rather than solved, for example duplicate UUIDs
  (:doc:`/developer/domain/records`).
* Abstractions exist only where the first release needs them:
  the storage and source ports, not a plugin framework or workflow
  engine.
