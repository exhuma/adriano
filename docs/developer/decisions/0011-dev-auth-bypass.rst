0011: A gated development login
===============================

:Status: Accepted
:Date: 2026-10-19

Context
-------

Developers and demos need to sign in as reader, reviewer or operator
without an identity provider,
but such a bypass must be impossible to enable by accident in
production.

Decision
--------

Follow ``module-dev-auth-bypass`` with independent gates:

* the backend accepts HS256 tokens only when
  ``ADRIANO_DEV_SHARED_SECRET`` is set, and selects the validator from
  the token's ``alg`` header, so RS256 never reaches the dev path;
* the ``/auth/dev`` router (token minting and role presets) is
  imported and mounted only when ``ADRIANO_DEV_AUTH_ENABLED`` is true
  *and* the secret is set;
* the frontend dev-login UI exists only when a build-time literal
  (``import.meta.env.DEV`` and ``VITE_DEV_AUTH``) is true, never through
  runtime configuration.

Dev tokens carry the same ``aud`` and ``iss`` as real tokens and go
through the same claim mapping and authorization.

Consequences
------------

* Both flags are off by default and the secret has no default.
* ``frontend/scripts/check-no-dev-auth.sh`` fails the production build
  if dev-login code reaches ``dist/``.
* With a real issuer configured, a dev token can impersonate any
  ``issuer|subject``; the secret must never be set in production.
  See :doc:`/developer/security`.
