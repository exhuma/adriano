Python API reference
====================

Reference for the backend package ``app``, generated from the
docstrings.
There is one page per module.
Narrative pages link here with ``:mod:`` rather than repeating what the
docstrings say.

Top-level modules
-----------------

Application wiring, configuration and cross-cutting helpers.
Everything that is not part of a package below lives here.

.. toctree::
   :maxdepth: 1

   app
   app.catalog_config
   app.cli
   app.composition
   app.config
   app.database
   app.errors
   app.main
   app.source_config
   app.tls
   app.validation_messages
   app.web

Authentication
--------------

Bearer-token validation, the dev-token path, push tokens and the
role-based permission rules.

.. toctree::
   :maxdepth: 1

   app.auth
   app.auth.deps
   app.auth.dev
   app.auth.oidc
   app.auth.push
   app.auth.rbac
   app.auth.tokens

Domain
------

The pure domain core: record parsing, validation, hashing and the
approval rules. It does no I/O.

.. toctree::
   :maxdepth: 1

   app.domain
   app.domain.approval
   app.domain.errata
   app.domain.fields
   app.domain.frontmatter
   app.domain.hashing
   app.domain.issues
   app.domain.records
   app.domain.relationships
   app.domain.titles
   app.domain.validation
   app.domain.values

Routers
-------

The HTTP layer. Each module owns one group of routes and delegates
to services.

.. toctree::
   :maxdepth: 1

   app.routers
   app.routers.auth_dev
   app.routers.candidates
   app.routers.decisions
   app.routers.facets
   app.routers.health
   app.routers.me
   app.routers.records
   app.routers.sources

Schemas
-------

Pydantic request and response models of the HTTP API.

.. toctree::
   :maxdepth: 1

   app.schemas
   app.schemas.approval
   app.schemas.auth
   app.schemas.records
   app.schemas.sources

Services
--------

Business orchestration over the domain, the source ports and the
storage port.

.. toctree::
   :maxdepth: 1

   app.services
   app.services.approval_view
   app.services.decisions
   app.services.dev_roles
   app.services.diff
   app.services.errata_view
   app.services.ingest
   app.services.intake
   app.services.intake_checks
   app.services.poll_plan
   app.services.poll_trigger
   app.services.polling
   app.services.record_detail
   app.services.record_relationships
   app.services.registrations
   app.services.search
   app.services.seed_synthetic
   app.services.seed_synthetic_errata
   app.services.seed_synthetic_gen
   app.services.seed_synthetic_text
   app.services.sources_view

Sources
-------

The provider-neutral source port and its filesystem and GitLab
adapters.

.. toctree::
   :maxdepth: 1

   app.sources
   app.sources.filesystem
   app.sources.gitlab
   app.sources.gitlab_api
   app.sources.gitlab_settings
   app.sources.port
   app.sources.registry

Storage
-------

The storage port and its PostgreSQL implementation.

.. toctree::
   :maxdepth: 1

   app.storage
   app.storage.errata_values
   app.storage.port
   app.storage.postgres
   app.storage.postgres.convert
   app.storage.postgres.errata
   app.storage.postgres.events
   app.storage.postgres.migrations
   app.storage.postgres.models
   app.storage.postgres.records
   app.storage.postgres.registrations
   app.storage.postgres.search
   app.storage.postgres.store
   app.storage.values

