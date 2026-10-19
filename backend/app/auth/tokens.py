"""
Bearer-token validation: pick the validator by the unverified ``alg``.

Per ``module-dev-auth-bypass`` the validator is selected from the
token's **unverified** header, never by trying validators in turn:

- ``RS256`` -> the OIDC/JWKS validator (:mod:`app.auth.oidc`); never
  the dev validator.
- ``HS256`` -> the dev validator (:mod:`app.auth.dev`), only when
  ``ADRIANO_DEV_SHARED_SECRET`` is set; otherwise 401.
- anything else (``none``, ``HS512``, ``ES256`` ...) -> 401.

Both paths return verified claims that feed the same
:func:`app.auth.deps.principal_from_claims` mapping.

Semantics: HTTP 503 (:class:`~app.errors.AuthUnavailableError`) means
the server can authenticate nobody right now (no mechanism configured,
or the IdP is unreachable); HTTP 401
(:class:`~app.errors.AuthenticationError`) means this request's
credentials are not acceptable.

Public API: :class:`AuthStatus`, :func:`auth_status`,
:func:`ensure_configured`, :func:`verify_token`.
"""

from enum import StrEnum
from typing import Any

import jwt

from app.auth.dev import decode_dev_token
from app.auth.oidc import OidcValidator
from app.config import Settings
from app.errors import AuthenticationError, AuthUnavailableError

__all__ = ["AuthStatus", "auth_status", "ensure_configured", "verify_token"]


class AuthStatus(StrEnum):
    """Which token validators are configured (reported by ``/healthz``)."""

    OIDC = "oidc"
    DEV = "dev"
    OIDC_AND_DEV = "oidc+dev"
    UNCONFIGURED = "unconfigured"


def auth_status(settings: Settings) -> AuthStatus:
    """
    Describe the configured token validators.

    :param settings: Application settings.
    :returns: The status.
    """
    oidc = bool(settings.oidc_authority)
    dev = bool(settings.dev_shared_secret)
    if oidc and dev:
        return AuthStatus.OIDC_AND_DEV
    if oidc:
        return AuthStatus.OIDC
    if dev:
        return AuthStatus.DEV
    return AuthStatus.UNCONFIGURED


def ensure_configured(settings: Settings) -> None:
    """
    Refuse requests when no token validator is configured.

    :param settings: Application settings.
    :raises AuthUnavailableError: If neither OIDC nor the dev secret is
        configured.
    """
    if auth_status(settings) is AuthStatus.UNCONFIGURED:
        raise AuthUnavailableError(
            "authentication is not configured; set ADRIANO_OIDC_AUTHORITY "
            "(or, for local development only, ADRIANO_DEV_SHARED_SECRET)",
            code="auth_unconfigured",
        )


def _algorithm(token: str) -> object:
    """
    Read the unverified ``alg`` header.

    :param token: Raw token.
    :returns: The header value (unverified, may be anything).
    :raises AuthenticationError: If the token is malformed.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(
            "malformed bearer token", code="invalid_token"
        ) from exc
    return header.get("alg")


def verify_token(
    token: str, settings: Settings, oidc: OidcValidator | None
) -> dict[str, Any]:
    """
    Validate a bearer token with the validator its ``alg`` selects.

    :param token: Raw bearer token.
    :param settings: Application settings.
    :param oidc: The OIDC validator, ``None`` when OIDC is not
        configured.
    :returns: The verified claims.
    :raises AuthenticationError: If the token is not acceptable.
    :raises AuthUnavailableError: If the IdP cannot be reached.
    """
    alg = _algorithm(token)
    if alg == "RS256":
        if oidc is None:
            raise AuthenticationError(
                "RS256 tokens are not accepted: OIDC is not configured",
                code="invalid_token",
            )
        return oidc.decode(token)
    if alg == "HS256":
        return decode_dev_token(token, settings)
    raise AuthenticationError(
        "unsupported token algorithm", code="invalid_token"
    )
