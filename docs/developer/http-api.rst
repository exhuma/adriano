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
   Every ``/api/v1`` route needs an ``Authorization: Bearer <token>``
   header.
   In production the token is an RS256 JWT from the configured OIDC
   provider; with dev auth enabled, an HS256 token minted with
   ``task mint-dev-token`` is accepted as well.
   See :mod:`app.auth.tokens`.
   Without any configured validator, every ``/api/v1`` route answers
   503.

Push tokens
   Candidate intake (``/api/v1/candidates``) is the exception.
   It accepts only the per-registration CI push token, never an OIDC
   or dev token, and a push token grants no read access.
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

The dev-only routes (``/auth/dev/token`` and ``/auth/dev/roles``) are
mounted only when dev auth is enabled and are therefore not part of
the reference below.

Endpoints
---------

The reference is generated at build time by ``docs/conf.py`` and
grouped by tag.

.. openapi:: ../_generated/openapi.json
   :group:
