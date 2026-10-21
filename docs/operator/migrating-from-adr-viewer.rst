Migrating from the ADR viewer
=============================

This page is for operators who ran the previous ``ADR_VIEWER_``
service and are moving to Adriano.
There is no automatic converter.
Write a new :doc:`catalog file <catalog-file>` by hand and validate it
with :doc:`the check-config command <cli>` before pointing production
traffic at it.

What changed for clients
------------------------

The most significant change is that Adriano never reads a source while
answering a request.
The old service scraped its source on every ``/adr/`` request.
Adriano serves everything from its own index; only a
:doc:`poll <polling>` or a :doc:`CI push <ci-push>` talks to a source.

``GET /``
   The old service redirected to ``/docs``.
   Adriano serves the web interface at ``/`` and has no redirect.

``GET /adr/``
   Returned HTML, or JSON when asked for with an ``Accept`` header or
   ``?json=true``.
   Replaced by ``GET /api/v1/records`` (search and list) and
   ``GET /api/v1/records/{id}`` (detail).
   Both return JSON only; the web interface renders the HTML.

``GET /healthz``
   Unchanged path, still public.
   The answer now reports each subsystem; see
   :doc:`health-and-logging`.

``GET /docs``
   Moved to ``GET /api/docs``.
   The schema is at ``GET /openapi.json``.
   Both are public and contain no records.

Settings
--------

The old service configured one source through ``ADR_VIEWER_*``
environment variables.
Adriano reads any number of named sources from ``catalog.yaml``
(located by :envvar:`ADRIANO_CONFIG_FILE`) and uses ``ADRIANO_``
environment variables for everything else.
No variable maps one-to-one, but everything the old ones carried has
a new home.

Which repository or path to scrape
   A ``sources`` entry in the catalog file.
   See :doc:`sources`.

Source credentials
   The ``token_env`` field of that entry names an environment
   variable that holds the token.
   The token itself is never written to the catalog file.

Which branch counts as authoritative
   ``published_ref`` on the source entry: a branch name, or
   ``"@project-default"`` for GitLab.

SSO audience (``adr_viewer``)
   :envvar:`ADRIANO_OIDC_AUDIENCE`.
   The default is the same value, ``adr_viewer``, so an existing
   identity-provider client registration keeps working unchanged.

Roles file (``admin`` role grants ``read``)
   ``rbac.roles`` in the catalog file, for example
   ``admin: [read, operate]``.
   Adriano adds the separate ``operate`` permission (starting polls)
   and a reviewer grant (``approval_policy.reviewers``).
   The old service had no approval workflow.

Development sign-in fixture
   :envvar:`ADRIANO_DEV_AUTH_ENABLED` and
   :envvar:`ADRIANO_DEV_SHARED_SECRET`.
   Never enable these in production; see :doc:`authentication`.

Container workers
   :envvar:`ADRIANO_WORKERS`.
   The old image started five worker processes; Adriano defaults to
   four.
   Raise it if your traffic needs more.
