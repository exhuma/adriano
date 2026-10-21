Troubleshooting
===============

Start with two commands; they explain most problems:

.. code-block:: sh

   curl -fsS https://adriano.example.com/healthz
   docker compose run --rm --no-deps adriano adriano check-config

Each entry below gives the symptom, the likely cause and what to
check.

Start-up
--------

The container exits right after start (or restarts in a loop)
   *Cause:* a setting is invalid, or the database update failed.
   Adriano checks its settings when it starts and refuses to run with
   an invalid one.

   *Check:* the container log
   (``docker compose logs adriano``, or ``kubectl logs`` of the pod
   and of the ``migrate`` init container).
   The last lines name the setting:

   ``database_url  Field required``
      :envvar:`ADRIANO_DATABASE_URL` is not set.
      With Compose it comes from ``deploy/compose.defaults.env`` and
      ``.env``; check that both files are found next to
      ``docker-compose.yml``.
   ``database_url  URL scheme should be 'postgres', 'postgresql', ...``
      The address does not start with ``postgresql://``.
   ``ADRIANO_OIDC_AUTHORITY must look like https://host[:port][/path]``
      The authority has a query, fragment, user name, password,
      quotes or spaces.
      Use the plain base URL of the identity provider.
   ``ADRIANO_OIDC_AUTHORITY and ADRIANO_OIDC_CLIENT_ID must be set together``
      Set the missing one, or unset both.
      Without both, the web UI cannot sign anyone in.
   ``ADRIANO_STATIC_DIR=... has no index.html``
      :envvar:`ADRIANO_STATIC_DIR` points at a folder that is not the
      web UI.
      Unset it to use the folder built into the image.

   A failing schema update logs the database error and exits with
   code 2; see :doc:`upgrades`.
   Usually the database is unreachable, the credentials are wrong or
   the user lacks privileges.
   With Compose, ``docker compose ps -a`` shows whether ``db`` ever
   became healthy.

``/healthz`` answers 503
   *Cause:* the database is unreachable.

   *Check:* ``docker compose ps`` for the health of ``db``;
   the database address, user and password
   (:doc:`configuration`).

``/healthz`` shows ``config: missing``
   *Cause:* the catalog file is not where Adriano expects it.

   *Check:* :envvar:`ADRIANO_CATALOG_FILE_HOST` points at an existing
   file on the Docker host; recreate the container after fixing it.

The catalog shows the sample records instead of yours
   *Cause:* :envvar:`ADRIANO_CATALOG_FILE_HOST` is unset, so the demo
   catalog is used.

   *Check:* set it in ``.env`` and recreate the container.
   Records already indexed from the samples stay in the catalog
   (removed registrations are only disabled).
   If this happened before going live, start over with an empty
   database: ``docker compose down -v`` deletes **all** data.

Sign-in and access
------------------

Nobody can sign in; the UI says no identity provider is configured
   *Cause:* ``/healthz`` reports ``auth: unconfigured``.

   *Check:* set :envvar:`ADRIANO_OIDC_AUTHORITY` (and
   :envvar:`ADRIANO_OIDC_CLIENT_ID` for the web UI), then recreate
   the container.

The sign-in page offers no way to sign in
   *Cause:* :envvar:`ADRIANO_OIDC_CLIENT_ID` is not set.

   *Check:* set it and recreate the container.

Sign-in at the provider works, but the UI then fails or loops
   *Cause:* the redirect URI is not registered at the provider, or the
   browser blocks the provider's endpoints.

   *Check:* the provider registers
   ``https://<your Adriano address>/auth/callback`` exactly;
   the provider's token and key endpoints share the origin of
   :envvar:`ADRIANO_OIDC_AUTHORITY`;
   the browser console for blocked requests.

Every request answers 401 ``invalid_token``
   *Cause:* the token's audience or issuer does not match, or it is
   not signed with RS256.

   *Check:* decode an access token and compare ``aud`` with
   :envvar:`ADRIANO_OIDC_AUDIENCE` and ``iss`` with the provider's
   issuer (or :envvar:`ADRIANO_OIDC_ISSUER`).

Requests answer 503 ``auth_unavailable``
   *Cause:* Adriano cannot reach the identity provider's
   discovery document or signing keys.

   *Check:* network access from the Adriano container to
   :envvar:`ADRIANO_OIDC_AUTHORITY`; for an internal certificate
   authority, :envvar:`SSL_CERT_FILE`.

Signed in, but every page says "permission required" (403)
   *Cause:* none of the user's roles grants ``read`` in ``rbac``,
   or the roles are not where :envvar:`ADRIANO_OIDC_ROLES_CLAIM`
   points.

   *Check:* ``check-config`` lists the configured roles;
   decode an access token and find the role list.
   ``/healthz`` showing ``rbac: empty`` means no role grants
   anything.

Users are signed out after reloading the page
   Expected: sessions are kept in browser memory only.
   With an active provider session, signing in again needs no
   password.

``/healthz`` shows ``auth: dev`` or ``auth: oidc+dev``
   *Cause:* :envvar:`ADRIANO_DEV_SHARED_SECRET` is set.

   *Check:* remove it at once; see
   :ref:`verify-dev-auth-off`.

Sources and polls
-----------------

A source shows "Disabled" with a configuration problem
   *Cause:* its catalog entry is invalid, or its token variable is
   not set.

   *Check:* ``check-config`` prints the exact problem.
   Fix it, then recreate the container.

   .. figure:: /_static/screenshots/sources-operator-config-problem.png
      :alt: The Sources table where a GitLab source is Disabled, with a
            Configuration problem message and a hint to set the token
            variable and restart.

      A source disabled because its token variable is not set.

A poll ends ``failed``
   *Cause:* the source could not be listed: GitLab unreachable, token
   expired or lacking access (401/403), or a folder root missing or
   unreadable.

   *Check:* the problem shown on the Sources page or printed by
   ``adriano poll --source <id>``.
   Previously indexed records are kept; poll again after fixing it.

A poll ends ``partial``
   *Cause:* some projects or files could not be listed or read.

   *Check:* the problem list of the poll; for GitLab, groups or
   projects that no longer exist or that the token cannot see.

Record pages say the content may be out of date
   *Cause:* the last poll failed or was partial, or the last success
   is older than :envvar:`ADRIANO_STALE_AFTER_MINUTES`.

   *Check:* that the poll schedule runs (``adriano poll`` exit codes
   in your cron log), and the Sources page.

An ``ownership_conflict`` warning in a poll
   *Cause:* two registrations contain the same file;
   the one listed first in the catalog file keeps it.

   *Check:* the ``scope`` of both registrations.

Approval
--------

Every record says the approval policy is missing
   *Cause:* ``approval_policy`` is missing or invalid in the catalog
   file; ``/healthz`` shows ``policy: missing`` or ``invalid``.

   *Check:* ``check-config``; fix the policy and restart the container.

A reviewer cannot decide
   *Cause:* they are neither in ``reviewers.users`` nor hold a role in
   ``reviewers.roles``; or the record has no valid uuid; or they are
   the recorded author and self-approval is off.

   *Check:* their ``issuer|subject`` and roles against the policy.

CI pushes
---------

Push answers 401 ``invalid_push_token``
   *Cause:* wrong or rotated token, unknown or disabled
   ``source_id``, or the token variable is not set in the container.

   *Check:* ``check-config`` warns about unset push token variables;
   compare the CI variable with the container's value.

Push answers 403 ``push_disabled`` or ``project_out_of_scope``
   *Cause:* the registration lacks ``push`` in ``intake``, or the
   project is not in its ``scope``.

   *Check:* the registration in the catalog file.

All other push errors are listed in
:ref:`operator/ci-push:What the answer means`.
