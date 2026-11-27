HTTP API
========

The backend serves a JSON HTTP API under ``/api/v1``.
This page documents the API, rendered from the OpenAPI document that
the FastAPI application itself generates.
Narrative pages for the Python side live in :doc:`api/index`.

Conventions
-----------

Base path
   All catalog routes are below ``/api/v1``.
   ``/healthz`` is the only unversioned route and is public.

Authentication
   Every ``/api/v1`` user route needs the ``__Host-adriano-session``
   cookie, set by the sign-in flow below.
   Requests with an unsafe method also need the header
   ``X-Adriano-CSRF: 1``; an ``Origin`` header, if present, must match
   the request's own origin (403 ``csrf_failed`` otherwise).
   An ``Authorization`` header is ignored on these routes.
   A missing, unknown or ended session answers 401.
   See :mod:`app.auth.deps`.
   Without any configured sign-in mechanism (:mod:`app.auth.status`),
   every ``/api/v1`` route answers 503.

Push tokens
   Candidate intake (``/api/v1/candidates``) is the exception.
   It accepts only the per-registration CI push token
   (``Authorization: Bearer``), never a session, and a push token
   grants no read access.
   See :mod:`app.auth.push`.

Errors
   Errors are JSON objects ``{"detail": "<message>"}``.
   Errors that carry a machine-readable reason add ``"code"``;
   recovery advice adds ``"hint"``, and some errors add further
   members, such as the ``issues`` list of a refused candidate.
   The status code of each error class is registered in
   :mod:`app.errors`.

Interactive docs
   A running instance serves Swagger UI at ``/api/docs`` and the raw
   OpenAPI document at ``/openapi.json``.
   Both are public and contain no catalog data.

Sign-in routes
   The backend, as OIDC client, serves these outside ``/api``
   (:mod:`app.routers.auth`); they win over the SPA fallback.

   ``GET /auth/login?return_to=<path>``
      Redirects to the provider (code, PKCE S256, state, nonce).
      ``return_to`` must be a relative path; anything else becomes
      ``/``.
      404 when OIDC is not configured.
   ``GET /auth/callback``
      Exchanges the code, validates the tokens, creates the session
      and sets the cookie.
      It answers a landing page that loads ``/auth/landing.js``, which
      navigates to the target (a ``SameSite=Strict`` cookie is not sent
      on the redirect chain from the provider).
      Failures answer a small HTML page with status 400.
   ``GET /auth/session``
      Always 200: ``{"authenticated": true, "expires_at": ...}`` or
      ``{"authenticated": false}``.
      It never refreshes tokens and needs no CSRF header.
   ``POST /auth/logout``
      Needs the CSRF header.
      Deletes the session, clears the cookie, revokes the refresh
      token (best effort) and returns ``{"end_session_url": ...}``.

The dev-only routes (``POST /auth/dev/login`` and
``GET /auth/dev/roles``) are mounted only when dev auth is enabled and
are therefore not part of the reference below.
``POST /auth/dev/login`` needs the CSRF header, takes the identity
fields of ``DevIdentity`` and answers 204 with a dev session cookie.

Endpoints
---------

The reference is generated at build time by ``docs/conf.py`` and
grouped by tag.

.. openapi:: ../_generated/openapi.json
   :group:
