0020: One container image for the API and the web UI
====================================================

:Status: Accepted
:Date: 2026-10-21

Context
-------

Adriano was built as two images: an nginx image for the Vue SPA that
proxied ``/api`` to a FastAPI image, plus a one-shot migration service
in Compose.
Operators had to deploy and version three moving parts, wire a
``backend`` host name between them, and learn a second set of setting
names (``OIDC_*``) that only the nginx image read.
No image was published, so every operator built their own.

Decision
--------

Ship one image, ``ghcr.io/exhuma/adriano``:

* Uvicorn serves the API and the built SPA from one process on port
  8000.
  API routes win; any other ``GET`` falls back to ``index.html`` for
  history-mode routing.
* ``/config.js`` is rendered by the backend from the same
  ``ADRIANO_*`` settings as the API, so one ``ADRIANO_OIDC_AUTHORITY``
  feeds both token validation and the SPA's sign-in.
  The bundle is built once and carries no environment-specific value.
* The backend sets the Content-Security-Policy and the other security
  headers that nginx used to add, deriving the identity provider's
  origin from the authority.
* ``adriano serve`` (the image command) applies migrations first,
  under a PostgreSQL advisory lock, then starts Uvicorn.
  ``ADRIANO_MIGRATE_ON_START=false`` and ``adriano migrate`` give
  platforms such as Kubernetes a separate migration step.
* Releases are CalVer (``YYYY.M.D``) images on GHCR with moving
  ``stable``, ``beta``, ``alpha`` and ``rc`` channels, ``edge`` and
  ``sha-<short>`` for the main branch, and no ``latest``.

Alternatives considered
-----------------------

nginx and the API in one image under a process supervisor
   Keeps the old runtime split, but adds a supervisor, two processes
   to health-check and two log streams, and keeps the duplicated
   setting names.
   Rejected: more moving parts than serving static files from the
   application.
Two images (web and API)
   Allows scaling and updating the web tier on its own.
   Rejected: the SPA is small and static, the two always release
   together, and two images need a version-compatibility contract and
   an internal host name.

Consequences
------------

* Operators deploy and pin one artifact.
  Compose has two services (``db`` and ``adriano``); Kubernetes needs
  a Deployment, a Service and an optional CronJob.
* The SPA is served by Python.
  That is adequate for an internal tool; a CDN or ingress cache in
  front can take over static assets without changing the image.
* Migrate-on-start couples start-up to schema changes.
  The advisory lock makes concurrent starts safe, and the opt-out
  keeps a restricted application database user possible.
  A schema change is still forward-only: rolling back needs a database
  backup (:doc:`/operator/upgrades`).
* The CSP lives in application code and is covered by tests rather
  than by a template that only runs inside the container.
* Setting names are uniform; the ``OIDC_*`` container names and
  ``ADRIANO_FRONTEND_*`` settings are gone.
