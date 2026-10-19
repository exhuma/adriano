"""
Dev-only HS256 tokens signed with ``ADRIANO_DEV_SHARED_SECRET``.

Follows ``module-dev-auth-bypass``: HS256 tokens are accepted **only**
when the shared secret is configured (it has no default and must be
unset in production). Dev tokens enforce the same ``aud`` and ``iss``
as real tokens and carry their roles at the configured roles claim
path, so they go through exactly the same claim mapping and
authorization code as real IdP tokens.

Dev issuer: ``ADRIANO_OIDC_ISSUER`` when set, else :data:`DEV_ISSUER`
(``adriano-dev``). With a real issuer configured, a dev token can
therefore act as any ``issuer|subject`` -- which is why the secret must
never be set in production.

Tokens are minted by ``adriano mint-dev-token`` (CLI) and by
``POST /auth/dev/token`` (mounted only when ``ADRIANO_DEV_AUTH_ENABLED``
is true; see :mod:`app.routers.auth_dev`).

Public API: :data:`DEV_ISSUER`, :data:`DEFAULT_MINUTES`,
:class:`DevIdentity`, :func:`dev_issuer`, :func:`decode_dev_token`,
:func:`mint_dev_token`.
"""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import jwt

from app.auth.oidc import REQUIRED_CLAIMS
from app.config import Settings
from app.errors import AuthenticationError

__all__ = [
    "DEFAULT_MINUTES",
    "DEV_ISSUER",
    "DevIdentity",
    "decode_dev_token",
    "dev_issuer",
    "mint_dev_token",
]

#: ``iss`` of dev tokens when ``ADRIANO_OIDC_ISSUER`` is not set.
DEV_ISSUER = "adriano-dev"

#: Default dev token lifetime in minutes.
DEFAULT_MINUTES = 60


@dataclass(frozen=True, slots=True)
class DevIdentity:
    """
    The identity a dev token asserts.

    :param sub: Subject.
    :param name: Display name, if any.
    :param email: Email, if any.
    :param roles: Role names.
    """

    sub: str
    name: str | None = None
    email: str | None = None
    roles: Sequence[str] = ()


def dev_issuer(settings: Settings) -> str:
    """
    Return the issuer dev tokens carry and must match.

    :param settings: Application settings.
    :returns: ``ADRIANO_OIDC_ISSUER`` or :data:`DEV_ISSUER`.
    """
    return settings.oidc_issuer or DEV_ISSUER


def _nest(path: str, value: object) -> dict[str, Any]:
    """
    Build a claim mapping that holds *value* at a dotted *path*.

    :param path: Dotted claim path (for example ``realm_access.roles``).
    :param value: The value.
    :returns: The nested mapping.
    """
    head, _, rest = path.partition(".")
    return {head: _nest(rest, value) if rest else value}


def mint_dev_token(
    settings: Settings,
    identity: DevIdentity,
    *,
    minutes: int = DEFAULT_MINUTES,
    now: datetime.datetime | None = None,
) -> str:
    """
    Sign a dev token for *identity*.

    :param settings: Application settings (secret, audience, issuer,
        roles claim path).
    :param identity: The asserted identity.
    :param minutes: Lifetime in minutes.
    :param now: Issue time (default: now).
    :returns: The encoded token.
    :raises ValueError: If ``ADRIANO_DEV_SHARED_SECRET`` is not set.
    """
    if not settings.dev_shared_secret:
        raise ValueError("ADRIANO_DEV_SHARED_SECRET is not set")
    issued = now or datetime.datetime.now(datetime.UTC)
    claims: dict[str, Any] = {
        "iss": dev_issuer(settings),
        "aud": settings.oidc_audience,
        "sub": identity.sub,
        "iat": issued,
        "nbf": issued,
        "exp": issued + datetime.timedelta(minutes=minutes),
    }
    if identity.name:
        claims["name"] = identity.name
    if identity.email:
        claims["email"] = identity.email
    roles_claim = _nest(settings.oidc_roles_claim, list(identity.roles))
    claims.update(roles_claim)
    return jwt.encode(claims, settings.dev_shared_secret, algorithm="HS256")


def decode_dev_token(token: str, settings: Settings) -> dict[str, Any]:
    """
    Validate a dev HS256 token and return its claims.

    :param token: Raw bearer token.
    :param settings: Application settings.
    :returns: The verified claims.
    :raises AuthenticationError: If the secret is unset or the token is
        not acceptable.
    """
    secret = settings.dev_shared_secret
    if not secret:
        raise AuthenticationError(
            "HS256 tokens are not accepted", code="invalid_token"
        )
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=settings.oidc_audience,
            issuer=dev_issuer(settings),
            options={"require": list(REQUIRED_CLAIMS)},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError(
            "token has expired", code="token_expired"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(
            f"token rejected ({type(exc).__name__})", code="invalid_token"
        ) from exc
