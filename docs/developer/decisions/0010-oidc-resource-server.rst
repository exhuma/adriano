0010: Standard OIDC, stateless bearer tokens
============================================

:Status: Superseded in part by :doc:`0022-backend-for-frontend-session`.
   The SPA as a public client, in-memory tokens and bearer-token user
   authentication no longer apply; the backend's OIDC claim validation and
   the role mapping still do.
:Date: 2026-10-19

Context
-------

The deployment's existing SSO and RBAC had to be preserved,
and the specification forbade inventing a custom JWT validator.

Decision
--------

The backend is an OIDC resource server: it validates RS256 tokens with
PyJWT against the provider's discovery document and JWKS
(issuer, audience ``adr_viewer`` by default, and a configurable roles
claim path).
The SPA is a public client using Authorization Code + PKCE through
``oidc-client-ts`` and keeps tokens in memory.
Permissions (``read``, ``operate``) map from IdP roles in
``catalog.yaml``; reviewer eligibility comes from the approval policy,
never from read permission.

Consequences
------------

* No user table and no server session.
* An unreachable IdP answers 503, not 401, and never stops startup:
  discovery is lazy.
* A full page reload signs the user out; that is the price of never
  putting a token in browser storage.
* RP-initiated logout is not implemented.
