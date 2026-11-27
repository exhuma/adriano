"""
Which sign-in mechanisms are configured.

- OIDC: ``ADRIANO_OIDC_AUTHORITY`` is set (sign-in through the backend
  as a confidential client).
- Dev: ``ADRIANO_DEV_AUTH_ENABLED`` is true *and*
  ``ADRIANO_DEV_SHARED_SECRET`` is set, i.e. ``POST /auth/dev/login``
  is mounted and dev sessions are accepted.

Semantics: HTTP 503 (:class:`~app.errors.AuthUnavailableError`) means
the server can authenticate nobody right now (no mechanism configured,
or the IdP is unreachable); HTTP 401
(:class:`~app.errors.AuthenticationError`) means this request has no
acceptable session.

Public API: :class:`AuthStatus`, :func:`auth_status`,
:func:`dev_auth_active`, :func:`ensure_configured`.
"""

from enum import StrEnum

from app.config import Settings
from app.errors import AuthUnavailableError

__all__ = [
    "AuthStatus",
    "auth_status",
    "dev_auth_active",
    "ensure_configured",
]


class AuthStatus(StrEnum):
    """Which sign-in mechanisms are configured (reported by ``/healthz``)."""

    OIDC = "oidc"
    DEV = "dev"
    OIDC_AND_DEV = "oidc+dev"
    UNCONFIGURED = "unconfigured"


def dev_auth_active(settings: Settings) -> bool:
    """
    Tell whether the dev login is mounted and dev sessions accepted.

    :param settings: Application settings.
    :returns: Both dev switches are on.
    """
    return settings.dev_auth_enabled and bool(settings.dev_shared_secret)


def auth_status(settings: Settings) -> AuthStatus:
    """
    Describe the configured sign-in mechanisms.

    :param settings: Application settings.
    :returns: The status.
    """
    oidc = bool(settings.oidc_authority)
    dev = dev_auth_active(settings)
    if oidc and dev:
        return AuthStatus.OIDC_AND_DEV
    if oidc:
        return AuthStatus.OIDC
    if dev:
        return AuthStatus.DEV
    return AuthStatus.UNCONFIGURED


def ensure_configured(settings: Settings) -> None:
    """
    Refuse requests when no sign-in mechanism is configured.

    :param settings: Application settings.
    :raises AuthUnavailableError: If neither OIDC nor dev auth is
        configured.
    """
    if auth_status(settings) is AuthStatus.UNCONFIGURED:
        raise AuthUnavailableError(
            "authentication is not configured; set ADRIANO_OIDC_AUTHORITY "
            "(or, for local development only, ADRIANO_DEV_AUTH_ENABLED and "
            "ADRIANO_DEV_SHARED_SECRET)",
            code="auth_unconfigured",
        )
