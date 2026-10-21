0012: Per-registration push tokens for CI
=========================================

:Status: Accepted
:Date: 2026-10-19

Context
-------

CI pipelines are not users and have no OIDC identity,
yet their writes must be scoped to the registrations they belong to.

Decision
--------

Each registration lists env var names of its push tokens
(``push_tokens_env``).
Push intake accepts only these shared secrets, compared in constant
time; it never accepts OIDC or dev tokens, and push tokens are never
accepted by read routes.
A token authorizes writing candidates to its registration only.
Any client-supplied digest is ignored.

Consequences
------------

* A leaked push token can add candidates to one registration but
  cannot read the catalog, publish, or decide.
* Rotation is an operator task: list a second env var, deploy, remove
  the old one.
* There is no rate limit; every request, including refused ones,
  writes an ``intake_run`` row.
