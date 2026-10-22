"""
FastAPI dependencies: sessions, the authenticated principal, rights.

Users authenticate **only** with the ``__Host-adriano-session`` cookie
(Backend-for-Frontend, ADR 0022); an ``Authorization`` header is
ignored on user routes (CI push tokens are a separate scheme,
:mod:`app.auth.push`). :func:`get_principal` resolves the cookie
through :class:`~app.services.auth_sessions.SessionService` (which
refreshes OIDC tokens inline) and maps the session's verified claims
-- the IdP access token's, or a dev session's -- with
:func:`principal_from_claims`. Cookie-authenticated requests with an
unsafe method must pass :func:`app.auth.csrf.check_csrf` (HTTP 403).

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
:func:`get_oidc_validator`, :func:`get_idp_client`,
:func:`get_session_service`, :func:`get_login_service`,
:func:`get_principal`, :func:`get_permissions`,
:func:`require_permission`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Request

from app.auth.cipher import SessionCipher
from app.auth.cookies import SESSION_COOKIE, read_cookie
from app.auth.csrf import UNSAFE_METHODS, check_csrf
from app.auth.idp import IdpClient
from app.auth.oidc import OidcValidator, cached_oidc_validator
from app.auth.rbac import Permission, permissions_for
from app.auth.status import dev_auth_active, ensure_configured
from app.composition import (
    CatalogRuntime,
    get_catalog_runtime,
    get_session_store_provider,
)
from app.config import Settings, get_settings
from app.errors import (
    AuthenticationError,
    AuthUnavailableError,
    ForbiddenError,
    NotFoundError,
)
from app.services.auth_sessions import SessionPolicy, SessionService
from app.services.oidc_login import LoginService
from app.storage.session_port import SessionKind, SessionStoreProvider
from app.tls import ssl_context_from_settings

__all__ = [
    "Principal",
    "get_idp_client",
    "get_login_service",
    "get_oidc_validator",
    "get_permissions",
    "get_principal",
    "get_session_service",
    "principal_from_claims",
    "require_permission",
]


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
        settings.extra_ca_certs or (),
    )


def get_idp_client(
    settings: Settings = Depends(get_settings),
    oidc: OidcValidator | None = Depends(get_oidc_validator),
) -> IdpClient | None:
    """
    FastAPI dependency: the confidential OIDC client, if configured.

    Tests override this to inject a mocked token endpoint.

    :param settings: Application settings.
    :param oidc: The validator of the same provider.
    :returns: The client, or ``None`` without OIDC.
    """
    if (
        oidc is None
        or settings.oidc_client_id is None
        or settings.oidc_client_secret is None
    ):
        return None
    return IdpClient(
        oidc,
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        scope=settings.oidc_scope,
        ssl_context=ssl_context_from_settings(settings),
    )


def _accepted_kinds(
    settings: Settings, idp: IdpClient | None
) -> set[SessionKind]:
    """
    List the session kinds the current configuration accepts.

    :param settings: Application settings.
    :param idp: The OIDC client, if configured.
    :returns: The kinds.
    """
    kinds: set[SessionKind] = set()
    if idp is not None:
        kinds.add(SessionKind.OIDC)
    if dev_auth_active(settings):
        kinds.add(SessionKind.DEV)
    return kinds


def get_session_service(
    settings: Settings = Depends(get_settings),
    provider: SessionStoreProvider = Depends(get_session_store_provider),
    idp: IdpClient | None = Depends(get_idp_client),
) -> SessionService | None:
    """
    FastAPI dependency: the session service, if sessions are configured.

    :param settings: Application settings.
    :param provider: Session storage.
    :param idp: The OIDC client, if configured.
    :returns: The service, or ``None`` without ``ADRIANO_SESSION_KEY``.
    """
    if settings.session_key is None:
        return None
    return SessionService(
        provider,
        SessionCipher(settings.session_key),
        SessionPolicy.from_settings(settings),
        accepted=_accepted_kinds(settings, idp),
        idp=idp,
    )


def get_login_service(
    settings: Settings = Depends(get_settings),
    provider: SessionStoreProvider = Depends(get_session_store_provider),
    idp: IdpClient | None = Depends(get_idp_client),
    sessions: SessionService | None = Depends(get_session_service),
) -> LoginService:
    """
    FastAPI dependency: the OIDC sign-in flow.

    :param settings: Application settings.
    :param provider: Session storage.
    :param idp: The OIDC client.
    :param sessions: The session service.
    :returns: The service.
    :raises NotFoundError: If OIDC is not configured (HTTP 404).
    """
    if idp is None or sessions is None or settings.session_key is None:
        raise NotFoundError(
            "OIDC sign-in is not configured", code="oidc_not_configured"
        )
    return LoginService(
        provider, SessionCipher(settings.session_key), idp, sessions
    )


def get_principal(
    request: Request,
    settings: Settings = Depends(get_settings),
    sessions: SessionService | None = Depends(get_session_service),
) -> Principal:
    """
    FastAPI dependency: authenticate the session cookie.

    Synchronous on purpose: FastAPI runs it in a worker thread, so the
    database lookup and a (rare) token refresh or discovery/JWKS fetch
    never block the event loop.

    :param request: The request (cookie, method, CSRF headers).
    :param settings: Application settings.
    :param sessions: The session service.
    :returns: The principal.
    :raises AuthUnavailableError: If authentication is not configured
        or the IdP is unreachable (HTTP 503).
    :raises AuthenticationError: If there is no usable session (HTTP
        401).
    :raises ForbiddenError: If an unsafe request fails the CSRF check
        (HTTP 403, code ``csrf_failed``).
    """
    ensure_configured(settings)
    cookie = read_cookie(request, SESSION_COOKIE)
    if cookie is None:
        raise AuthenticationError(
            "authentication required: sign in first",
            code="not_authenticated",
            token_presented=False,
        )
    if request.method in UNSAFE_METHODS:
        check_csrf(request)
    if sessions is None:
        raise AuthUnavailableError(
            "sessions are not configured; set ADRIANO_SESSION_KEY",
            code="auth_unconfigured",
        )
    active = sessions.authenticate(cookie)
    return principal_from_claims(
        active.claims, roles_claim=settings.oidc_roles_claim
    )


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
