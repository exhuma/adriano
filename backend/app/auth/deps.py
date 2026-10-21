"""
FastAPI dependencies: the authenticated principal and permissions.

Identity comes from verified token claims only; no user is stored.
Real (RS256) and dev (HS256) tokens produce their claims through
:func:`app.auth.tokens.verify_token` and then share this module's
mapping (:func:`principal_from_claims`) and authorization
(:func:`require_permission`).

Claim mapping:

- ``issuer`` / ``subject`` -- ``iss`` / ``sub`` (required).
- ``display`` -- ``name``, else ``preferred_username``, else ``sub``.
- ``email`` -- ``email``, unless the token says
  ``email_verified: false`` (then ``None``).
- ``roles`` -- the list of strings at the dotted
  ``ADRIANO_OIDC_ROLES_CLAIM`` path (default ``roles``; Keycloak:
  ``realm_access.roles``). A missing path or a non-list value yields no
  roles; non-string items are ignored.

Permissions come from the ``rbac`` section loaded at startup
(:mod:`app.auth.rbac`); no configuration means no permissions.

Public API: :class:`Principal`, :func:`principal_from_claims`,
:func:`get_oidc_validator`, :func:`get_principal`,
:func:`get_permissions`, :func:`require_permission`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.oidc import OidcValidator, cached_oidc_validator
from app.auth.rbac import Permission, permissions_for
from app.auth.tokens import ensure_configured, verify_token
from app.composition import CatalogRuntime, get_catalog_runtime
from app.config import Settings, get_settings
from app.errors import AuthenticationError, ForbiddenError

__all__ = [
    "Principal",
    "get_oidc_validator",
    "get_permissions",
    "get_principal",
    "principal_from_claims",
    "require_permission",
]

_bearer = HTTPBearer(auto_error=False, description="OIDC access token")


@dataclass(frozen=True, slots=True)
class Principal:
    """
    The authenticated caller, from verified token claims.

    :param issuer: Token ``iss``.
    :param subject: Token ``sub``.
    :param display: Human-readable name.
    :param email: Email, if the token carries one (not marked
        unverified).
    :param roles: Role names, sorted and unique.
    """

    issuer: str
    subject: str
    display: str
    email: str | None
    roles: tuple[str, ...]


def _claim_at(claims: Mapping[str, Any], path: str) -> object:
    """
    Follow a dotted path through nested claim mappings.

    :param claims: Verified claims.
    :param path: Dotted path.
    :returns: The value, or ``None`` if the path does not exist.
    """
    value: object = claims
    for part in path.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)  # pyright: ignore[reportUnknownMemberType]
    return value


def _roles(claims: Mapping[str, Any], path: str) -> tuple[str, ...]:
    """
    Extract the role names at the configured claim path.

    :param claims: Verified claims.
    :param path: Dotted roles claim path.
    :returns: Sorted, unique role names.
    """
    value = _claim_at(claims, path)
    if not isinstance(value, list):
        return ()
    items: list[object] = list(value)  # pyright: ignore[reportUnknownArgumentType]
    return tuple(sorted({item for item in items if isinstance(item, str)}))


def _text(claims: Mapping[str, Any], key: str) -> str | None:
    """
    Read a non-empty string claim.

    :param claims: Verified claims.
    :param key: Claim name.
    :returns: The value, or ``None``.
    """
    value = claims.get(key)
    return value if isinstance(value, str) and value else None


def principal_from_claims(
    claims: Mapping[str, Any], *, roles_claim: str
) -> Principal:
    """
    Map verified claims to a :class:`Principal`.

    :param claims: Verified claims (``iss`` and ``sub`` present).
    :param roles_claim: Dotted roles claim path.
    :returns: The principal.
    :raises AuthenticationError: If ``iss`` or ``sub`` is not a string.
    """
    issuer = _text(claims, "iss")
    subject = _text(claims, "sub")
    if issuer is None or subject is None:
        raise AuthenticationError(
            "token lacks a usable iss or sub claim", code="invalid_token"
        )
    email = _text(claims, "email")
    if claims.get("email_verified") is False:
        email = None
    display = (
        _text(claims, "name") or _text(claims, "preferred_username") or subject
    )
    return Principal(
        issuer=issuer,
        subject=subject,
        display=display,
        email=email,
        roles=_roles(claims, roles_claim),
    )


def get_oidc_validator(
    settings: Settings = Depends(get_settings),
) -> OidcValidator | None:
    """
    FastAPI dependency: the OIDC validator, if OIDC is configured.

    Tests override this to inject mocked discovery and keys.

    :param settings: Application settings.
    :returns: The cached validator, or ``None``.
    """
    if not settings.oidc_authority:
        return None
    return cached_oidc_validator(
        settings.oidc_authority,
        settings.oidc_issuer,
        settings.oidc_audience,
        settings.tls_verify,
    )


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
    oidc: OidcValidator | None = Depends(get_oidc_validator),
) -> Principal:
    """
    FastAPI dependency: authenticate the bearer token.

    Synchronous on purpose: FastAPI runs it in a worker thread, so the
    (rare) discovery/JWKS fetch never blocks the event loop.

    :param credentials: The ``Authorization: Bearer`` credentials.
    :param settings: Application settings.
    :param oidc: The OIDC validator, if configured.
    :returns: The principal.
    :raises AuthUnavailableError: If authentication is not configured
        or the IdP is unreachable (HTTP 503).
    :raises AuthenticationError: If the token is missing or not
        acceptable (HTTP 401).
    """
    ensure_configured(settings)
    if credentials is None or not credentials.credentials:
        raise AuthenticationError(
            "authentication required: send an Authorization: Bearer token",
            code="not_authenticated",
            token_presented=False,
        )
    claims = verify_token(credentials.credentials, settings, oidc)
    return principal_from_claims(claims, roles_claim=settings.oidc_roles_claim)


def get_permissions(
    principal: Principal = Depends(get_principal),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
) -> frozenset[Permission]:
    """
    FastAPI dependency: the caller's permissions.

    :param principal: The authenticated caller.
    :param runtime: Startup state (``rbac`` section).
    :returns: Granted permissions (none without configuration).
    """
    rbac = runtime.config.rbac if runtime is not None else None
    return permissions_for(rbac, principal.roles)


def require_permission(
    permission: Permission,
) -> Callable[..., Principal]:
    """
    Build a dependency that requires *permission*.

    Use as ``Depends(require_permission(Permission.READ))``.

    :param permission: The required permission.
    :returns: A dependency returning the authenticated principal.
    """

    def _check(
        principal: Principal = Depends(get_principal),
        granted: frozenset[Permission] = Depends(get_permissions),
    ) -> Principal:
        """
        Refuse callers without the permission.

        :param principal: The authenticated caller.
        :param granted: The caller's permissions.
        :returns: The principal.
        :raises ForbiddenError: If the permission is not granted.
        """
        if permission not in granted:
            raise ForbiddenError(
                f"the '{permission}' permission is required; ask an "
                f"administrator for a role that grants it",
                code="permission_required",
            )
        return principal

    return _check
