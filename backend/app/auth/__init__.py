"""
Authentication and authorization (Backend-for-Frontend, ADR 0022).

- :mod:`app.auth.oidc` -- validation of the IdP's RS256 tokens
  (discovery document + cached JWKS).
- :mod:`app.auth.idp` -- the backend as a confidential OIDC client
  (authorization URL, code exchange, refresh, revocation, logout URL).
- :mod:`app.auth.cipher` -- Fernet encryption of session data at rest.
- :mod:`app.auth.cookies` -- the ``__Host-`` session and sign-in
  cookies.
- :mod:`app.auth.csrf` -- CSRF checks of cookie-authenticated requests.
- :mod:`app.auth.pages` -- the sign-in landing and error pages.
- :mod:`app.auth.dev` -- dev-only session claims (``POST
  /auth/dev/login``).
- :mod:`app.auth.status` -- which sign-in mechanisms are configured.
- :mod:`app.auth.rbac` -- role -> permission mapping and reviewer
  eligibility.
- :mod:`app.auth.deps` -- FastAPI dependencies (:class:`Principal`,
  ``get_principal``, ``require_permission``, the session services).
- :mod:`app.auth.push` -- constant-time CI push-token checks for
  candidate intake (a separate scheme, never a session).
"""
