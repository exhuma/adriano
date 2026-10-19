"""
Authentication and authorization.

- :mod:`app.auth.oidc` -- RS256 bearer tokens from the configured IdP
  (discovery document + cached JWKS).
- :mod:`app.auth.dev` -- dev-only HS256 tokens (shared secret), minted
  by ``adriano mint-dev-token`` or ``POST /auth/dev/token``.
- :mod:`app.auth.tokens` -- validator selection by the unverified
  ``alg`` header and claim mapping.
- :mod:`app.auth.rbac` -- role -> permission mapping and reviewer
  eligibility.
- :mod:`app.auth.deps` -- FastAPI dependencies (:class:`Principal`,
  ``get_principal``, ``require_permission``).
"""
