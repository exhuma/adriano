Architecture
============

This page shows how Adriano fits together and why it is shaped this way.
It is written for architects who evaluate fit and risk,
and for developers who need the big picture before changing code.

The architecture was fixed with the product owner on 2026-10-19
and last revisited on 2026-10-21.
The reasoning behind each choice is recorded in :doc:`decisions/index`;
the domain model it serves is described in :doc:`domain/index`.

System context
--------------

Adriano indexes architecture decision records (Markdown files with YAML
frontmatter) that live in other systems,
keeps its own copy in PostgreSQL,
and runs an approval workflow on top of that copy.

.. mermaid::

   flowchart LR
     reader["Reader or reviewer<br/>(browser)"]
     operator["Operator"]
     ci["CI pipeline"]
     idp["OIDC identity provider"]
     subgraph adriano["Adriano"]
       spa["Frontend<br/>Vue SPA, served by the API"]
       api["Backend API<br/>FastAPI, stateless"]
       poll["Polling<br/>CLI job or operator trigger"]
     end
     db[("PostgreSQL")]
     gitlab["GitLab projects"]
     fs["ADR folder on disk"]

     reader -- "loads the app, calls /api" --> spa
     reader -- "signs in: Auth Code + PKCE" --> idp
     spa -- "same-origin /api calls" --> api
     api -- "fetches discovery and JWKS" --> idp
     ci -- "pushes candidates with a push token" --> api
     operator -- "schedules or triggers" --> poll
     poll -- "reads the published ref" --> gitlab
     poll -- "reads the published tree" --> fs
     poll -- "writes published rows" --> db
     api -- "reads and writes catalog data" --> db

Readers and reviewers
   Use the single-page app in a browser.
   They sign in at the organisation's OIDC provider;
   the SPA sends the access token as a bearer token to the API.

Operators
   Deploy Adriano, write ``catalog.yaml``,
   schedule ``adriano poll`` (cron or a Kubernetes CronJob)
   and can trigger a poll from the Sources page.
   See :doc:`/operator/index`.

CI pipelines
   Push candidate ADRs from feature branches through
   ``PUT`` or ``POST /api/v1/candidates``,
   authenticated with a per-registration push token.

GitLab and the filesystem
   Are the two source types.
   Adriano only ever reads them, and only from the polling code path.

OIDC provider
   Issues RS256 access tokens.
   The backend is a resource server: it validates tokens against the
   provider's JWKS and never takes part in the login flow.

PostgreSQL
   Holds everything Adriano knows: registrations, record rows,
   immutable content snapshots, decision events and intake runs.

In the bundled ``docker-compose.yml`` stack the single ``adriano``
container is the only published entry point.
It serves the SPA and the API from one process and applies the
migrations when it starts.

Concern map and layering
------------------------

The backend is one deployable (a modular monolith).
Each concern lives in its own package,
and calls flow only downward:

.. mermaid::

   flowchart TD
     ui["frontend/<br/>Vue 3 + Vuetify SPA"]
     routers["app.routers<br/>HTTP boundary, schemas"]
     auth["app.auth<br/>OIDC, dev bypass, push tokens, RBAC"]
     services["app.services<br/>ingest, polling, intake,<br/>search, decisions"]
     domain["app.domain<br/>pure parsing, hashing,<br/>links, approval"]
     sources["app.sources<br/>adapter port, filesystem, gitlab"]
     storage["app.storage<br/>store port, PostgreSQL implementation"]
     db[("PostgreSQL")]

     ui -- "bearer token, JSON" --> routers
     routers -- "authenticates and authorizes" --> auth
     routers -- "calls" --> services
     services -- "uses pure functions" --> domain
     services -- "reads and writes through the port" --> storage
     services -. "polling only" .-> sources
     storage -- "SQL" --> db

:mod:`app.domain`
   Pure logic with no I/O: frontmatter parsing and validation,
   the canonical digest, relationship resolution,
   approval-state evaluation, erratum body parsing.
   It imports neither FastAPI, SQLAlchemy nor httpx,
   so it is tested with plain unit tests.

:mod:`app.services`
   Use cases.
   They take a ``CatalogStore`` from :mod:`app.storage.port` and plain
   values, and return plain dataclasses.
   They never import FastAPI.

:mod:`app.storage`
   :mod:`app.storage.port` defines the DB-neutral ``CatalogStoreProvider``
   and ``CatalogStore`` protocols and their value types;
   :mod:`app.storage.postgres` is the only implementation.
   No ORM object crosses the port.

:mod:`app.sources`
   :mod:`app.sources.port` defines the provider-neutral ``SourceAdapter``
   protocol; :mod:`app.sources.filesystem` and :mod:`app.sources.gitlab`
   implement it.
   :mod:`app.sources.registry` maps a source type to its settings validator
   and adapter factory.
   Everything GitLab-specific stays inside the ``gitlab*`` modules.

:mod:`app.routers` and :mod:`app.schemas`
   The HTTP boundary: request parsing, Pydantic response models,
   permission dependencies.
   Domain errors from :mod:`app.errors` are mapped to HTTP statuses with a
   flat ``{detail, code}`` body.

:mod:`app.auth`
   Token validation (:mod:`app.auth.tokens` picks the validator by the
   token's ``alg``), claim mapping, RBAC and push-token checks.

:mod:`app.composition`
   The composition root.
   It is the only module that names concrete implementations
   (the PostgreSQL store, the default source registry)
   and the only one that hands the process environment to the
   configuration loader.
   Both the FastAPI lifespan and the ``adriano`` CLI build their object
   graph here.

Two rules follow from this layering and are enforced by tests
(see :doc:`invariants`):

* Browse, search, detail, diff and sources requests reach
  ``services → storage → PostgreSQL`` only.
  They never construct or call a source adapter.
* Source adapters are opened only by :mod:`app.services.polling`.
  Push intake never calls an adapter.

Data flows
----------

Poll path
~~~~~~~~~

Polling reads each registration's configured published ref
and keeps the published rows in step with it.

.. mermaid::

   sequenceDiagram
     participant T as cron, CronJob or operator
     participant P as PollingService
     participant A as Source adapter
     participant S as CatalogStore (PostgreSQL)

     T->>P: poll_all() or poll_source(id)
     P->>S: start intake_run (own unit of work)
     P->>A: list_projects()
     A-->>P: projects, complete flag
     P->>A: list_documents(project, stored tokens)
     A-->>P: documents with change tokens, complete flag
     P->>A: fetch() changed documents only
     A-->>P: exact bytes, source URL
     P->>P: prepare_document(): parse, validate, hash, render
     P->>S: lock_registration(source_id)
     P->>S: upsert published rows, refresh tokens
     P->>S: delete rows missing from a complete listing
     P->>S: finish intake_run, set last_status (own unit of work)

Registrations are polled one after another in configuration order,
because the first registration that yields a ``(project, path)`` owns
it; later ones skip it with an ``ownership_conflict`` warning.
Each registration runs in three phases:

1. **Run log.** An ``intake_run`` row is started in its own unit of
   work, so a rolled-back write never loses the log.
2. **Collect.** No transaction and no lock are held while the adapter
   lists and fetches, with bounded concurrency.
   Documents whose change token is unchanged are not fetched at all.
3. **Apply.** Under the registration's advisory lock, in one
   transaction: ingest the fetched documents, rewrite moved change
   tokens and reconcile deletions.

Nothing is deleted unless the project listing was complete,
and within a project nothing is deleted unless its document listing was
complete.
A failed or partial poll therefore keeps all prior content.
Polling never deletes candidates.

Push path
~~~~~~~~~

CI submits candidates from branches other than the published ref.

.. mermaid::

   sequenceDiagram
     participant CI as CI job
     participant R as candidates router
     participant I as intake service
     participant G as ingest (shared with polling)
     participant S as CatalogStore (PostgreSQL)

     CI->>R: PUT or POST /api/v1/candidates, push token
     R->>I: submit_candidate()
     I->>I: authenticate token, check body, scope and ref
     I->>G: prepare_document(): parse, validate, hash, render
     I->>I: document UUID must equal adr_uuid
     I->>S: lock_registration(source_id)
     I->>G: ingest_document() as CANDIDATE
     G->>S: put revision, upsert candidate row
     I->>S: record intake_run
     R-->>CI: 200 or 201 with server digest and issues

Push intake and polling share :mod:`app.services.ingest`:
``prepare_document`` parses, validates, hashes and renders,
``ingest_document`` stores the snapshot and upserts the row.
Push always writes a candidate row, so it can never replace or delete a
published row, and it never calls a source adapter.
The full check order and error codes are in the :mod:`app.services.intake`
docstring.

Read path
~~~~~~~~~

.. mermaid::

   sequenceDiagram
     participant B as Browser (SPA)
     participant R as records router
     participant Q as search / record_detail services
     participant S as CatalogStore (PostgreSQL)

     B->>R: GET /api/v1/records?q=...&filters
     R->>Q: search_records()
     Q->>S: count + one page query (FTS, filters, approval state)
     S-->>Q: rows
     Q-->>R: page of items
     R-->>B: JSON
     B->>R: GET /api/v1/records/{id}
     R->>Q: get_record_detail()
     Q->>S: record, siblings, related rows, errata, decisions
     S-->>Q: rows
     Q-->>R: assembled detail
     R-->>B: JSON

A search is a count query plus one page query,
with the approval state computed in SQL
(plus one lookup for the titles of the decisions that erratum hits
correct).
A detail request runs a handful of targeted queries whose number is
bounded by the record's own links and errata, never by catalog size.
No read ever reaches a source.
See :doc:`performance` for the measured cost.

Decision path
~~~~~~~~~~~~~

.. mermaid::

   sequenceDiagram
     participant B as Reviewer (SPA)
     participant R as decisions router
     participant D as decisions service
     participant S as CatalogStore (PostgreSQL)

     B->>R: POST /api/v1/records/{id}/decisions
     R->>D: record_decision(action, comment, expected_digest)
     D->>S: load record and identity events
     D->>D: policy, eligibility, approvable, self-approval, digest
     D->>S: append_decision() with ON CONFLICT DO NOTHING
     alt no earlier decision for identity and digest
       S-->>D: event stored
       D-->>R: decision
       R-->>B: 201 with the event
     else another decision won the race
       S-->>D: DecisionExistsError
       R-->>B: 409 already_decided
     end

The decision binds to the record's logical identity and the digest of
its current content.
The server sets the event id and timestamp.
See :doc:`domain/approval` for the rules.

Storage and concurrency
-----------------------

PostgreSQL (psycopg 3, SQLAlchemy 2, Alembic) is the only stateful
service.
It covers both durable storage and full-text search:
``record.search`` is a weighted ``tsvector`` maintained by a trigger and
indexed with GIN.
Alembic owns the schema; tables are never created from the ORM models
outside tests.
See :doc:`domain/schema` for the tables.

Concurrent writers are made safe by three mechanisms:

Per-registration advisory lock
   All writes for one registration (the apply phase of a poll, a push)
   run inside ``CatalogStoreProvider.lock_registration``, which takes
   ``pg_advisory_xact_lock(namespace, hashtext(source_id))``.
   The lock lives exactly as long as the transaction,
   so it is released on commit or rollback and works across processes
   and replicas.
   Two pollers, or a poll racing a push, for the same registration
   serialize instead of interleaving.

``ON CONFLICT`` upserts
   Record rows are upserted against partial unique indexes
   (published by location, candidates by identity and ref).
   Revisions are inserted with ``ON CONFLICT DO NOTHING``,
   since a digest names the same content forever.

Unique constraints as the arbiter
   ``uq_decision_event_identity_digest`` allows one decision per
   identity and digest.
   A losing concurrent decision gets HTTP 409, never a silent
   overwrite.
   ``POST /api/v1/candidates`` and ``delivery_id`` deduplication use
   the same pattern.

Stateless replicas
~~~~~~~~~~~~~~~~~~

The backend holds no state between requests:
identity comes from the bearer token,
catalog data from PostgreSQL,
and configuration from ``catalog.yaml`` and the environment at startup.
Any number of replicas and Uvicorn workers can run against one database
(the container default is four workers).
Scheduled polling runs as a separate one-shot process,
never as a timer inside a web worker,
so adding replicas never multiplies polls.

What we deliberately do not run
-------------------------------

No distributed queue or event bus
   Polling is a periodic, idempotent batch job,
   serialized per registration by the advisory lock.
   A queue would add an operational dependency without solving a
   problem this workload has.

No separate search cluster
   PostgreSQL full-text search meets the latency target at the
   catalog's scale (thousands of records, not millions);
   see :doc:`performance`.
   Elasticsearch or OpenSearch would double the stateful services to
   operate and back up.

No microservices
   The package boundaries above already separate parsing, sources,
   intake, persistence and the web layer.
   Network boundaries would add latency, versioning and partial-failure
   modes with no benefit for one team at this scale.

The trade-off is explicit: one database is a single failure domain for
the whole catalog.
Backup, restore and retention of the audit data are operator concerns,
documented in :doc:`/operator/index`.

Frontend architecture
---------------------

The frontend is a Vue 3 single-page app built with Vite and TypeScript,
using Vuetify 4 for components and theming
(see :doc:`decisions/0017-vuetify-first`).

Routes
   ``/`` (search landing page), ``/records/:id`` (record or erratum
   page), ``/sources`` (registration status),
   ``/auth/callback`` (OIDC redirect target) and a not-found route.

State
   No global store.
   Composables (``useSearchQuery``, ``useRecordDetailView``,
   ``useDecision``, ``useMe`` and others) hold view state;
   search terms, filters and sort live in the URL query so they can be
   shared.

API access
   ``src/api/index.ts`` is a small ``fetch`` wrapper with a pluggable
   token provider and 401 handling.
   Response types are generated from the backend's OpenAPI schema
   into ``src/types/openapi.ts`` with ``npm run gen:types``.

Authentication
   ``oidc-client-ts`` runs Authorization Code + PKCE as a public client.
   Tokens are kept in memory only, so a full page reload signs the user
   out (see :doc:`security`).

Runtime configuration
   The API process renders ``/config.js`` from its settings (OIDC
   settings; the API is always on the same origin) and adds the
   Content-Security-Policy with the identity provider's origin to every
   response.
   The dev-login switch is a build-time literal and is never part of
   runtime configuration.

Rendered Markdown
   The API returns HTML that was sanitized with nh3 at ingest;
   only that field is rendered with ``v-html``.
