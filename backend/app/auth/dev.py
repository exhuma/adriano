"""
Dev-only sign-in: claims for a dev session.

Follows ``module-dev-auth-bypass``: ``POST /auth/dev/login``
(:mod:`app.routers.auth_dev`) is mounted only when
``ADRIANO_DEV_AUTH_ENABLED`` is true *and* ``ADRIANO_DEV_SHARED_SECRET``
is set (both unset in production), and dev sessions are accepted only
while both still are (:func:`app.auth.status.dev_auth_active`). A dev
session holds claims only -- no IdP tokens -- built here in the shape
of a real access token (``iss``, ``sub``, ``name``, ``email`` and the
roles at the configured roles claim path), so they go through exactly
the same claim mapping and authorization code as real sessions.

Dev issuer: ``ADRIANO_OIDC_ISSUER`` when set, else :data:`DEV_ISSUER`
(``adriano-dev``). With a real issuer configured, a dev session can
therefore act as any ``issuer|subject`` -- which is why dev auth must
never be enabled in production.

Public API: :data:`DEV_ISSUER`, :class:`DevIdentity`,
:func:`dev_issuer`, :func:`dev_claims`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.config import Settings

__all__ = ["DEV_ISSUER", "DevIdentity", "dev_claims", "dev_issuer"]

#: ``iss`` of dev sessions when ``ADRIANO_OIDC_ISSUER`` is not set.
DEV_ISSUER = "adriano-dev"


@dataclass(frozen=True, slots=True)
class DevIdentity:
    """
    The identity a dev session asserts.

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
    Return the issuer of dev sessions.

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


def dev_claims(settings: Settings, identity: DevIdentity) -> dict[str, Any]:
    """
    Build the claims of a dev session.

    :param settings: Application settings (issuer, roles claim path).
    :param identity: The asserted identity.
    :returns: Claims shaped like a real access token's.
    """
    claims: dict[str, Any] = {
        "iss": dev_issuer(settings),
        "sub": identity.sub,
    }
    if identity.name:
        claims["name"] = identity.name
    if identity.email:
        claims["email"] = identity.email
    claims.update(_nest(settings.oidc_roles_claim, list(identity.roles)))
    return claims
