# Standalone coding-agent prompt

Build a new decision-record catalog from scratch. You have no access to the
source code of the existing application. Treat this document as the complete
description of its behavior and compatibility requirements.

The replacement is intended to serve multiple teams. It should be simple
enough to deliver a useful first release within a few days. Make choices
that support that release; document and defer larger ideas.

## Scope and phase rules

The first release is governance-first: it must support candidate submission,
accept/reject decisions, publication polling, and a useful catalog. Do not
turn this into a complete governance platform.

Implement **Phase 1 only** unless the product owner explicitly authorizes a
later phase. At Phase 1 completion, demonstrate the working product, report
which exit criteria passed, list deferred ideas, and stop for user review.
Do not continue automatically because tests pass or time remains.

Every phase must deliver a coherent, user-friendly product. Clean UI,
accessible controls, visible system status, useful errors, and recovery paths
are acceptance requirements in every phase, not optional polish.

### Phase 1: usable governance catalog

Include only:

- Config-file registration of multiple sources of the initial source type,
  with an explicit scope and published/default ref for each registration.
- Read registrations and one approval policy from one documented
  configuration file at startup. Configuration changes require restart; do
  not build live configuration editing.
- Polling of published/default refs and authenticated CI `POST`/`PUT`
  candidate intake from non-default branches.
- One shared parsing, validation, hashing, persistence, and indexing path.
- Candidate and published states. An accepted candidate is authoritative
  for implementation before publication.
- One formal reviewer decision per content hash: accept or reject. A single
  global config-file policy identifies eligible users or existing SSO roles.
  A rejection applies to that hash; changed content needs a new decision.
  No quorum, source-specific overrides, or approval-management UI.
- Canonical content hash, durable approval history, unchanged-content
  promotion, and snapshot diff from the last accepted/rejected version.
- Search, detail pages, and only these Phase 1 filters: source/project,
  candidate versus published, and needs approval.
- Basic typed lifecycle links and legacy `deprecates` compatibility.
- Deployment authentication/authorization, health status, and operator
  documentation needed to run this phase.

Do not add an admin UI, multiple approval stages, notifications, webhooks,
arbitrary connector plugins, advanced graph views, extensive policy rules,
or an LLM feature in Phase 1.

### Later-scope backlog (uncommitted)

These are possible future directions, not scheduled phases or promises. Do
not implement them in Phase 1. The product owner will choose and scope any
follow-up iteration after reviewing Phase 1:

- Additional source types, webhooks, and event-driven intake.
- Source-configuration and approval-policy administration UI.
- More complex approval rules, multi-stage review, notifications, and
  revocation workflows.
- Advanced lifecycle graph views, validation, and search facets.
- Optional local LLM assistance, such as semantic search or suggested links.

Every authorized follow-up iteration must get its own narrow scope,
demonstrable user workflow, acceptance criteria, and explicit user review
gate. Do not build a generic workflow engine, connector marketplace,
plugin framework, or abstractions solely for these possible futures.

### Feature-creep controls

- Treat Phase 1 scope and exit criteria as hard boundaries.
- Do not add “while here” features, extra configuration, or dependencies
  unless required by a Phase 1 acceptance criterion.
- When new requirements arise, state the smallest safe assumption, record
  the larger request as deferred work, and continue. Stop only for a genuine
  blocker to Phase 1 correctness, security, or usability.
- Do not broaden edge-case handling beyond the explicit Phase 1 contracts.
  Preserve invalid records and report useful errors; defer sophisticated
  remediation workflows and exhaustive graph validation.
- Keep design/reconnaissance bounded. Present a concise architecture and
  resolve only blockers before implementing Phase 1.

## Product goal

Build a reader-focused catalog for architecture and design decisions, with
the Phase 1 candidate accept/reject workflow defined below.

Decisions are Markdown files with YAML frontmatter. Some live in the
repository of the project they concern, so maintainers can author them in
place and project archival naturally removes those records. Cross-project
decisions live in other configured sources, such as a dedicated central
repository with its own source registration and scope.

Register source adapters behind a small, product-neutral interface. The
initial source type is identified in the source-registration requirements
below. The interface must support polling and push intake without exposing
provider-specific API details to the catalog, approval workflow, or
persistence layer.

This is a read-only catalog for ADR content. Candidate submission and
accept/reject actions are separate workflows stored by the application;
authors do not edit approval metadata in Markdown. Do not implement in-app
ADR editing, notifications, or lifecycle graph visualization in Phase 1.

## User decisions

- Prioritize readers over authors.
- Use a search-first landing page with filters.
- Search across titles, Markdown content, and useful metadata.
- Phase 1 filters: source/project, candidate versus published, and needs
  approval.
- Show compact, scannable search results and a readable record detail page.
- Make basic related decisions and errata links easy to follow.
- Include project-local and central records through separately configured
  source registrations and scopes.
- Support scheduled/operator-triggered polling and authenticated CI push
  intake through the same source abstraction.
- Poll only each registration's configured published/default refs.
- Accept candidate records from branches other than the published/default
  ref, and allow them to be formally accepted before publication.
- Do not call a source adapter during normal browsing or search.
- Preserve the deployment's SSO/RBAC access control.
- Keep approval/sign-off separate from authored Markdown.
- Bind every approval to a canonical SHA-256 of the complete ADR content,
  independent of the Git commit or repository path.
- Acceptance may happen on a candidate before it is on the published/default
  ref; the accepted candidate is authoritative for implementation.
- Identical content promoted to the published/default ref keeps its hash and
  acceptance history; changed content requires new approval/acceptance.
- Show a snapshot-based diff when content changes after approval/acceptance.
- Display legacy `signed-off-by` values as unverified historical metadata;
  they do not satisfy an approval rule.
- Provide a filter for ADRs whose current content still requires approval.
- Aim for P95 under one second for interactive browsing and search.
- Migration of routes and runtime is acceptable. The legacy ADR file
  structure is the compatibility requirement.

## Legacy application behavior

The old application was a Python 3.12 / FastAPI service packaged in a
Docker container. It used Uvicorn, with five workers in its container
entrypoint, and exposed a health-check endpoint at `/healthz`.

Its primary route was `/adr/`:

- It returned HTML by default.
- It returned JSON when the `Accept` header contained
  `application/json` or when `?json=true` was supplied.
- It scraped its configured source while handling this route.
- `/` redirected to `/docs`.

The old route and runtime behavior are context, not requirements. Preserve
`/healthz` if practical for deployment health checks, but you may design
new routes and a new runtime. Document any API migration.

The old deployment used `ADR_VIEWER_`-prefixed source configuration. The
replacement may use a new product-neutral configuration model. Keep source
credentials secret, scoped to registrations, and protected by normal TLS
certificate validation.

## Legacy ADR file compatibility

Existing project-local records are Markdown files under:

    doc/decisions/

The old crawler searched recursively below that path. It selected files
whose filename matched:

    ^\d{4}-\d{2}-\d{2}-(.*)\.md$

For example:

    doc/decisions/2024-12-24-use-postgresql.md

The filename date is not necessarily authoritative metadata. Do not use it
as a substitute for a missing `decision-date` without clearly labelling it
as inferred.

Files use YAML frontmatter delimited by lines containing `---`, followed by
a Markdown body. Existing fields are:

- `uuid`: UUID string; expected by the old parser.
- `decision-date`: optional ISO date, conventionally `YYYY-MM-DD`.
- `signed-off-by`: optional list of people, commonly email addresses.
- `deprecates`: optional single UUID referring to another decision.

The old parser warned when date or sign-off metadata was absent, reported
missing UUIDs as errors, and warned about unknown fields. It could fail on
malformed YAML or malformed dates/UUIDs. The replacement must handle an
invalid record without making the whole catalog unavailable.

Preserve existing files without requiring maintainers to rewrite them before
they can be indexed. In particular, map legacy `deprecates: UUID` to the
new obsolescence relationship and report that it is a legacy alias.

Deprecate `signed-off-by` as an approval mechanism. Continue parsing and
displaying its values on legacy records, visibly labelled “Legacy sign-off
(unverified)”. Never infer an authenticated approver, approval timestamp,
approval policy, or current approval from those values. New authors should
not need to add or maintain this field.

The old application did not define a title field. For display, support an
optional explicit `title`; if missing, derive a display title from the first
Markdown H1 and then from the filename as fallbacks. Clearly indicate
metadata validation problems without dumping every metadata field into
each search result.

## Record schema and lifecycle relationships

Keep Markdown as the raw record format and YAML frontmatter as metadata.
Provide a short, practical schema guide and example files.

Support, at minimum:

- stable record UUID
- title
- decision date
- record kind, defaulting to a normal decision for legacy files
- typed UUID relationships for updates and obsolescence
- separately identified erratum records linked to the decision they correct
- source project/repository, path, branch, and canonical source URL

The old `signed-off-by` field is compatibility-only, not a current approval
field. Approval and sign-off status live in the application persistence and
are displayed separately from authored document metadata.

Define relationship direction in the schema and UI:

- `updates` points from the newer decision to the earlier decision it
  updates.
- `obsoletes` points from the replacing decision to the decision it
  replaces.
- A separate erratum record has its own UUID and links to the decision it
  corrects. Derive the reverse “errata for this decision” listing in the
  catalog rather than requiring two conflicting sources of truth.

You may choose the exact YAML spelling and shape. Prefer simple arrays of
UUIDs for multi-record relationships. Explain the relationship semantics in
the schema documentation. Phase 1 UI only needs clear inbound/outbound links
on the detail page; defer graph visualization and advanced relationship
filters.

Derive display status from lifecycle links for Phase 1. Do not add a
standalone status field or build a generalized lifecycle engine.

Validate malformed UUIDs, duplicate UUIDs, and missing relationship targets.
Keep valid records browseable if another record has invalid metadata or a
broken link. Show concise, actionable validation messages. Defer cycle and
contradictory-graph analysis unless a concrete Phase 1 example requires it.

For a record without a valid UUID, retain it using a stable source identity,
such as source plus repository path. Do not invent a UUID that can be
mistaken for a maintainer-authored decision ID. Disable UUID-based
relationships for that record and report the issue. Keep fallback identity
handling simple in Phase 1; defer operator remediation tools for identity
conflicts.

## Independent approval and sign-off workflow

Formal approval is required, but it is not authored into the Markdown file.
Keep ADR content in registered sources and store approval policies and
approval events in durable application persistence. The approval UI is for
reviewers and operators; an ADR author should only need to write and submit
the Markdown record through the normal repository workflow.

Bind approval to the content, not to a Git commit, branch, repository path,
or mutable “current” record row. Define and document a versioned canonical
content-hash algorithm. At minimum, use SHA-256 over the complete UTF-8 ADR
file, including frontmatter and body, with line endings normalized to LF and
a UTF-8 BOM removed. Do not include Git commit IDs, project IDs, or paths in
the hash input. Store the algorithm/version with the digest, for example
`sha256-v1:<hex>`. Compute the digest from the exact source content that was
parsed and indexed. A content change must produce a different digest; moving
an unchanged file or committing the same bytes in a different commit must
not change it. Keep the algorithm version explicit so canonicalization can
be changed safely in the future.

Branch names, commit identifiers, source registration IDs, and source paths
are provenance and must not enter the digest. Therefore identical canonical
content submitted from a feature branch and later found on the published
default ref has the same digest and retains approval/acceptance evidence.

The digest identifies a content revision; it does not prove who authored the
content, when it was published, or that the approval persistence itself has
not been tampered with. Document those limits. If tamper evidence is required,
propose a separately scoped control such as protected audit storage or a
signed periodic audit export; do not imply ordinary persistence rows are
cryptographically immutable.

Use the logical ADR identity plus the content digest to scope approval
evidence. The logical identity is the ADR UUID within its source registration
and owning project/namespace. The digest identifies a content revision; it
does not replace the record UUID. For records without a valid UUID, use the
stable source identity for the record key and clearly explain its limitations.

Persist a durable approval history. Each decision event should include:

- stable authenticated identity, preferably issuer plus OIDC subject, not
  only a display name or email
- ADR identity and canonical content digest/hash version
- action: accepted or rejected
- timestamp from the server
- approval policy identity and policy version applied
- optional reviewer comment
- enough source metadata to trace the indexed record at approval time
- stable event ID

Keep decision events append-only. Restrict them to authenticated,
authorized reviewers. Disallow self-approval by default. For Phase 1, use
one global policy requiring one decision from an allowlist of users or
existing SSO roles. The assigned eligible reviewer records accept or reject
for the exact content hash. A rejection applies to that hash; changed content
has a new decision state. Do not add quorum, source overrides, multi-stage
approval, revocation workflows, or a generic workflow engine.

For Phase 1, acceptance means the reviewer accepts the exact content
revision as the decision to follow. Do not model a separate “reviewed” state.
Acceptance may happen while a record is still a candidate on a non-default
branch. Once accepted under its policy, the decision is accepted and may
guide implementation before publication. Display its state as “Accepted —
candidate” and include its branch/source provenance. When polling later finds
identical canonical content on the default ref, promote its publication
state to “Accepted — published” without changing the hash, losing approval
history, or requiring reapproval. If the published content has a different
hash, preserve the accepted candidate and the published revision as distinct
revisions; do not silently transfer acceptance. The new content needs its
own approval and acceptance. Define conflict handling when multiple
candidates for one ADR UUID have different hashes. Do not add a
candidate-management interface beyond showing candidates and allowing
authorized reviewers to accept or reject the selected content.

Make approval requirements explicit in one simple global configuration for
Phase 1. Do not implement per-source or per-record-kind overrides. Do not
silently treat a missing policy as “approval not required”; expose it as an
unconfigured-policy condition for operators.
The Phase 1 catalog must distinguish:

- approval not required by an explicit policy
- approval pending for the current content hash
- approval complete for the current content hash
- previously approved content whose current hash has changed
- rejected decision for the current content hash
- approval policy missing or invalid

Approval state is evaluated against the relevant stored revision, not a live
source read. For candidate records, identify the source and branch/ref whose
content was submitted. For published records, use the latest successfully
polled content from the configured published/default ref. Display source
freshness next to published state. When polling is stale or failed, do not
claim that the indexed revision is the latest published content.

Provide a reader-facing “Needs approval” filter that includes
records whose current content does not satisfy an applicable policy,
including pending, rejected, changed-after-acceptance, and missing-policy
records. Label these states clearly so a missing configuration is not
mistaken for a reviewer delay. Show legacy `signed-off-by` values as
unverified information, separate from the verified approval state.

Retain the exact canonical content snapshot associated with each approval
or acceptance event. When a later revision changes the hash, provide an
in-application unified diff or a stable link to a diff from the last
accepted/approved snapshot to the current indexed revision. The diff must
compare the exact snapshots, not rely on Git history being available. Label
both hashes and the indexed source/ref and freshness. For a candidate with
no prior acceptance, compare against its previous submitted revision when
available; otherwise indicate that no prior revision exists.

The application persistence layer is part of the first release because it
stores indexed content, candidate and publication state, source registrations,
approval policy, and the append-only approval history. Keep the storage
interface abstract; normal catalog logic must not depend on a particular
database product. An in-memory store is not acceptable for approval evidence.
Define backup, restore, retention, and migration expectations for audit data.

Do not assume a source platform's review approval is equivalent to the
catalog's formal ADR approval. It may be linked as supporting evidence, but
the catalog must retain its own hash-bound approval record unless the product
owner explicitly chooses and documents an integration that meets the same
audit contract.

## Source registrations and intake

Model each registered source as a separate configuration instance with:

- stable source ID and source type
- source-specific configuration and secret/credential reference
- scope/filter defining which repositories and ADR paths it owns
- published/default ref used for polling
- enabled intake mechanisms: polling, push, or both
- last successful poll, last attempted poll, and current status

Allow multiple registrations of the same source type. For example, two
registrations may point at different groups, repository sets, or filters.
A central cross-project ADR collection is another registration with a
different scope; it is not a special database or source type. Ensure
overlapping scopes do not silently create duplicate records. Define
deduplication and source ownership rules, using ADR UUID plus source
registration as provenance and detecting conflicting content hashes.

Implement GitLab as the initial source type. This is the only
product-specific source named in this prompt. Keep it behind the generic
source port, which supports both intake paths:

1. **Poll/scrape:** a scheduled or operator-triggered poll across all
   enabled registrations. Poll each registration's configured published/
   default ref only. Respect its configured scope and path filters. Use
   pagination, conditional fetching where available, bounded concurrency,
   timeouts, and retries. A complete successful poll may reconcile deletions.
   A partial or failed poll must preserve prior records for that registration.
2. **Push intake:** an authenticated HTTP API callable by CI. A candidate
   identity is scoped by source registration, owning project/repository, ADR
   UUID, and branch/ref. Provide idempotent `PUT` to create or replace the
   candidate revision for that identity and `POST` to create a new candidate,
   returning a conflict if it already exists. Requests include the source
   registration ID, project/repository identity, ADR UUID, branch/ref, and
   complete Markdown file. They may include a source event/delivery ID for
   retry deduplication. Verify the caller may write to that registration and
   that the document UUID matches the request. The server computes and
   validates the canonical content hash; never trust a client-supplied
   digest as authority.

Poll intake and push intake must converge on the same parsing, validation,
hashing, persistence, and relationship-indexing path. Neither intake path
may overwrite approval history. Normal browse/search requests must make no
source calls.

Candidate and published records have distinct state. Polling discovers
published/default-ref records only. Push intake can register candidates
from any branch. A candidate must not overwrite published content for the
same ADR UUID. Preserve candidate source/ref provenance and allow formal
approval and acceptance before the candidate is published. An accepted
candidate is authoritative for its decision and may guide implementation
before publication; show it as “Accepted — candidate”.

When a later poll finds identical canonical content on the published/default
ref, promote publication state to “Accepted — published” without changing
the hash or requiring reapproval. If the published content has a different
hash, retain the accepted candidate and published revision separately, flag
the divergence, and require approval/acceptance for the new content before
it is shown as accepted. Define handling for multiple candidates with the
same ADR UUID on different branches or projects. Do not infer promotion
from UUID alone; promotion must also match the owning project and content
hash within the configured source scope.

Keep provider-specific API calls, pagination formats, scopes, and credential
handling inside the adapter. Store configuration generically where possible
and validate source-type-specific settings at the adapter boundary. Scope
credentials to registrations and minimum required read/write access. Never
log secrets; validate TLS certificates. Do not reproduce the old behavior
of querying every visible project or making per-file serial requests.

Record poll and push outcomes, including source ID, candidate/published
identity, start/end time, status, and useful failure details. Ensure retries
are safe and concurrent intake/poll operations cannot corrupt state. Failed
or unauthorized operations must not erase previously indexed content.

## Architecture and persistence

Normal web requests must use the local catalog/index only.

Choose the simplest durable persistence and search implementation that fits
the deployment. Keep the domain-facing persistence interface abstract so
the source adapters and catalog workflows do not depend on a storage
product. Explain how the selected implementation handles concurrency,
multiple application replicas, backup, restore, and durable audit history.

Keep the following concerns separate:

- record parsing and validation
- source registration and source-adapter interface
- initial source adapter
- polling and push-intake orchestration
- candidate/published lifecycle and promotion
- indexing and reconciliation workflow
- abstract catalog persistence and search
- web routes and templates/UI
- authentication/authorization

Do not add a distributed queue, search cluster, event bus, or complex
microservice layout without a demonstrated requirement. For scheduled
indexing, prefer a documented external job/command over starting a timer in
every web worker. The manual refresh operation may be an authenticated
operator endpoint or command; choose one and document it.

## Optional local LLM integration

An optional, locally hosted LLM with an OpenAI-compatible API may be
configured by URL and model name in a later iteration. It is not a Phase 1
requirement and must not be required for startup, indexing, browsing, search,
approval, acceptance, or audit operations.

If implemented in an explicitly approved later iteration, limit it to
assistive features such as semantic search,
suggested related-record links, or a concise explanation of a diff since
acceptance. Keep all model output visibly labelled as generated suggestions;
never use it to decide approval, acceptance, lifecycle status, or source
truth. A timeout, unavailable endpoint, or malformed response must fall back
to normal deterministic behavior. Make sending ADR content to the endpoint
explicitly configurable and document that content may be disclosed to the
configured service. Do not send content to an unconfigured external provider.
Store endpoint credentials only in secret configuration and never log them.

Do not add an LLM call to the normal request path unless it can meet latency
targets and degrade gracefully. Record the proposed use cases and privacy
boundary before enabling it.

## Authentication and authorization

The old service used a platform authentication integration configured with:

- SSO/JWT audience: `adr_viewer`
- roles file: `roles.toml`
- development auth file: `dev-auth.toml`
- service name: `bb`

Its role file defined an `admin` role with `read` permission. Its development
auth fixture mapped an `Admin User` to that role. The actual JWT validation
and identity-claim mapping were provided by a library outside this prompt.

Preserve the deployment's existing SSO/RBAC model. Do not ship a publicly
accessible catalog or invent a custom JWT validator. Use the existing
platform's validated identity integration or an approved deployment
authentication adapter. If its issuer, claims, or integration contract are
not available to you, identify that as a blocking deployment question
instead of guessing.

Readers must be authorized to read the catalog. Restrict source
registration/configuration and manual poll operations to authorized
operators. Restrict CI push credentials to their permitted source
registrations and candidate-write operation. Restrict approval/acceptance
actions to authorized reviewers; do not assume read permission grants any
write action. Provide a development-only auth fixture and clearly prevent
it from being used as a production identity source.

## UI requirements

Phase 1 UI scope is search, detail, and the three basic filters specified in
Scope and phase rules. Build a simple, comfortable browsing interface:

- Search is the primary landing-page control.
- Source/project, candidate/published, and needs-approval filters are visible
  and understandable; users can clear them easily.
- Search terms and Phase 1 filters should be shareable through URL query
  parameters.
- Results are paginated or otherwise bounded.
- Show title, source/project, candidate/published state, and approval state
  in results. Do not add date or lifecycle facets in Phase 1.
- A detail page renders Markdown and shows metadata, validation warnings,
  source link, inbound/outbound relationships, and errata.
- A detail page shows approval requirements, whether approvals apply to the
  currently indexed content hash, and the separate legacy-unverified
  `signed-off-by` values when present.
- Clearly distinguish candidate from published records. An accepted
  candidate is authoritative and may guide implementation before publication.
- Show source/ref provenance and make accepted candidates discoverable.
- When content changes after acceptance, display or link to a diff from the
  exact accepted snapshot to the current indexed snapshot.
- Provide a “Needs approval” filter for records whose current revision does
  not meet the single global approval policy.
- Show accept/reject state, reviewer identity, timestamp, policy summary,
  and source freshness.
- Provide loading, empty, error, and stale-index states.
- Make controls keyboard-operable and accessible.
- Sanitize rendered Markdown HTML. Do not mark untrusted rendered content
  safe without sanitization.
- Do not make color the only way to communicate status or validation.

## Phase 1 acceptance

The P95 target for search and ordinary browsing is under one second against
a representative dataset. Record the dataset size, environment, and
benchmark method. If no representative production dataset is available,
create a reproducible synthetic dataset and state its limitations.

Phase 1 is complete only when all of these are true:

1. Starting the app with documented configuration works from a clean
   checkout using the documented commands.
2. First-time users can find a record and understand its source, candidate/
   published state, approval state, and freshness without operator help.
3. Source polling failures, invalid candidate submissions, and accept/reject
   actions produce clear status and actionable recovery information.
4. The UI is keyboard-operable, responsive, and has deliberate loading,
   empty, success, stale, and error states.
5. Normal browse, search, filter, and detail requests make no source calls.
6. Polling runs across configured registrations and scans only their
   published/default refs.
7. Authorized operators can trigger polling; CI can submit candidates
   through authenticated, source-scoped `POST`/`PUT` intake.
8. Poll and push use the same parsing, validation, hashing, and persistence
   workflow.
9. Unchanged content is not needlessly fetched or reprocessed when source
   metadata permits change detection.
10. A source failure leaves prior successful content available and reports
   registration-specific indexing status.
11. A completed poll removes published records confirmed deleted from a
   source; an incomplete or inaccessible poll does not erase them.
12. Candidate intake never overwrites a published record for the same ADR ID.
13. Identical candidate content promoted to the default ref keeps its hash
    and acceptance history; changed content does not inherit acceptance.
14. Legacy files using `uuid`, `decision-date`, `signed-off-by`, and
    `deprecates` are readable.
15. Legacy `signed-off-by` values are labelled unverified and never count
    as authenticated approval.
16. The single global approval policy is documented, configured, and
    enforced; accept/reject history persists across restarts.
17. The approved content SHA-256 is reproducible across refs and source
    locations when the canonical file contents are unchanged.
18. Editing the content changes its digest and causes prior approvals not
    to count for the new current revision, while retaining the old history.
19. The “Needs approval” filter returns records with unmet, rejected,
    changed-after-acceptance, or unconfigured approval state.
20. The UI shows a reproducible diff from the last approved/accepted snapshot
    to changed current content, even without Git history.
21. When polling is stale or failed, the UI does not claim that the last
    indexed hash is the current published source revision.
22. Approval events identify the policy and preserve an auditable,
    append-only accept/reject history.
23. Missing or malformed metadata affects only the individual record.
24. Legacy `deprecates` and supported typed links are navigable from record
    details; no graph view is required.
25. Search and browse meet the P95 target or provide the measured gap and
    reproducible benchmark results.
26. SSO/RBAC protects catalog access, approval actions, operator polling, and
    CI push intake.
27. Container health checks, persistence, backups, and restore are
    documented.

## Phase 1 delivery and handoff

Deliver a runnable Phase 1 application, not just a proposal. Include only
the configuration, code, tests, samples, deployment files, and operator/user
documentation needed to pass the Phase 1 acceptance criteria.

Before implementation, provide a concise architecture and schema proposal.
Call out only genuine blockers, especially the SSO/JWT integration contract
and durable-storage constraints. Then implement Phase 1 without expanding
scope. At completion:

1. Demonstrate search, detail, candidate submission, accept/reject, snapshot
   diff, and identical-content promotion.
2. Report each Phase 1 acceptance criterion as pass, fail, or not measured.
3. Record measured search latency and test conditions.
4. List deferred requests and any known limitations without implementing
   them.
5. Stop and wait for explicit user review before starting any later work.

Do not implement the later-scope backlog during this task.
