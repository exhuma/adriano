0009: One configuration file, read at startup
=============================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

Sources, the approval policy and RBAC change rarely,
and the first release has no admin UI.
The legacy service used ``ADR_VIEWER_`` environment variables for a
single source.

Decision
--------

``catalog.yaml`` (path in ``ADRIANO_CONFIG_FILE``) holds ``sources``,
``approval_policy`` and ``rbac``; changes need a restart.
Everything else is an ``ADRIANO_``-prefixed environment variable.
Secrets are referenced by environment variable **name**
(``token_env``, ``push_tokens_env``), resolved at startup,
held as secret strings and never logged or stored.
Validation degrades per entry instead of stopping startup:
an invalid registration is disabled with a readable error,
a missing or invalid policy yields ``policy_missing`` everywhere,
and a missing ``rbac`` section grants nothing.

Consequences
------------

* ``adriano check-config`` validates a file before deployment.
* A broken registration never takes the rest of the catalog down;
  problems show in ``/healthz``, the startup log and the Sources page.
* Registrations removed from the file are disabled, never deleted,
  so their history stays.
* A missing policy is never mistaken for "approval not required".
