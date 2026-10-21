Health checks and logs
======================

The health endpoint
-------------------

``GET /healthz`` needs no sign-in and returns no records or secrets.
It is reachable on the same address as the web UI
(``https://<your Adriano address>/healthz``) and directly on the
container's port 8000.

.. code-block:: json

   {"status": "ok", "database": "ok", "config": "ok",
    "policy": "configured", "registrations": "synced",
    "rbac": "configured", "auth": "oidc",
    "version": "2026.10.1"}

The HTTP status is **200** while the database is reachable and
**503** when it is not.
Only the database decides the HTTP status:
configuration problems are reported in the body but keep the answer
at 200, because restarting the container would not fix them.
Wire readiness checks to the HTTP status, and alert on the body
fields.
Do not use it as a liveness check: restarting a container does not
bring the database back.

``status``
   ``ok``, or ``degraded`` when the database is unreachable.
``database``
   ``ok`` or ``unavailable``.
``config``
   The catalog file: ``ok``, ``missing`` (not found) or ``invalid``
   (cannot be read or parsed).
   Problems inside an otherwise readable file do not show here;
   run ``adriano check-config``.
``policy``
   The approval policy: ``configured``, ``missing`` or ``invalid``.
   Anything but ``configured`` blocks every approval decision.
``registrations``
   Whether the sources from the catalog file were stored at start-up:
   ``synced``; ``skipped`` (the catalog file could not be loaded);
   or ``failed`` (the database was unreachable at start-up).
   The value is only updated when the container restarts;
   restart it once the database is back (each ``adriano poll``
   stores the sources anyway).
``rbac``
   ``configured`` when at least one role grants a permission,
   ``empty`` when nobody can do anything.
``auth``
   Which sign-in methods the API accepts:
   ``oidc`` (production), ``unconfigured`` (nobody can sign in),
   or ``dev`` / ``oidc+dev``, which mean the development sign-in is
   active and **must never be seen in production**
   (see :doc:`authentication`).

``version``
   The release the container runs (``dev`` for a local build).
   Use it to confirm that a rollout reached every replica.

Any field reading ``unknown`` means Adriano did not finish its
start-up; check its log.

The web UI reads the same endpoint.
When Adriano is degraded or unreachable, or the catalog file or
approval policy has a problem, it shows a notice in the app bar.

Container health check
----------------------

The image declares a health check that calls ``/healthz`` every 10
seconds; the container is unhealthy when it fails (that is, when the
database is unreachable).
Kubernetes ignores this check and uses probes instead; the example in
:doc:`deploy/kubernetes` explains which probe uses which check.

Check the state with ``docker compose ps`` or
``docker inspect --format='{{.State.Health.Status}}' <container>``.

Logs
----

The container logs to standard output and standard error;
nothing is written to files inside the container.
Collect them with your container platform's log driver:

.. code-block:: sh

   docker compose logs -f adriano

Secret values (tokens, passwords) are never logged;
messages name the environment variable instead.

Log lines worth alerting on:

``authentication is not configured``
   Nobody can sign in; set :envvar:`ADRIANO_OIDC_AUTHORITY`.
``DEV AUTH ENABLED`` or ``dev HS256 tokens are accepted``
   The development sign-in is on.
   Never acceptable in production.
``catalog config <location>: <message>``
   A problem in the catalog file, logged at start-up (as an error
   when something is disabled, else as a warning).
``source registrations not synced``
   The database was unreachable at start-up.

The scheduled ``adriano poll`` prints its results to standard output
and its warnings and errors to standard error;
keep both (see :doc:`polling`).
