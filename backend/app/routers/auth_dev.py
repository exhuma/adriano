"""
Dev-only endpoints: ``POST /auth/dev/login`` and ``GET /auth/dev/roles``.

**Never enabled in production.** :func:`app.main.create_app` imports and
mounts this router only when ``ADRIANO_DEV_AUTH_ENABLED`` is true *and*
``ADRIANO_DEV_SHARED_SECRET`` is set, so the paths are a plain 404
otherwise. ``POST /auth/dev/login`` creates a dev session for any
requested identity -- that is the point of a dev login -- and sets the
same session cookie as a real sign-in (CSRF header required).
``GET /auth/dev/roles`` lists the loaded catalog's role names so the
dev sign-in dialog can offer presets that match this catalog.
"""

from fastapi import APIRouter, Depends, Response

from app.auth.cookies import set_session_cookie
from app.auth.csrf import require_csrf
from app.auth.deps import get_session_service
from app.auth.dev import DevIdentity, dev_claims
from app.composition import CatalogRuntime, get_catalog_runtime
from app.config import Settings, get_settings
from app.errors import AuthUnavailableError
from app.schemas.auth import DevLoginIn, DevRolesOut
from app.services.auth_sessions import SessionService
from app.services.dev_roles import dev_role_catalog
from app.storage.session_port import SessionKind

router = APIRouter(prefix="/auth/dev", tags=["dev-auth"])


@router.post(
    "/login",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(require_csrf)],
    responses={403: {"description": "CSRF check failed (csrf_failed)"}},
)
def dev_login(
    body: DevLoginIn,
    settings: Settings = Depends(get_settings),
    sessions: SessionService | None = Depends(get_session_service),
) -> Response:
    """
    Create a dev session for the requested identity.

    :param body: Subject, name, email and roles.
    :param settings: Application settings (issuer, roles claim path).
    :param sessions: The session service.
    :returns: 204 with the session cookie.
    :raises AuthUnavailableError: If no session key is configured.
    """
    if sessions is None:
        raise AuthUnavailableError(
            "dev auth has no ADRIANO_SESSION_KEY", code="auth_unconfigured"
        )
    identity = DevIdentity(
        sub=body.sub, name=body.name, email=body.email, roles=body.roles
    )
    cookie = sessions.create(SessionKind.DEV, dev_claims(settings, identity))
    response = Response(status_code=204)
    set_session_cookie(response, cookie)
    return response


@router.get("/roles", response_model=DevRolesOut)
def list_dev_roles(
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
) -> DevRolesOut:
    """
    List the role names of the loaded catalog for dev sign-in presets.

    Unauthenticated like the login route: the dev dialog calls it
    before anyone is signed in. It exposes role names and permissions
    only, never reviewer users.

    :param runtime: Startup state (loaded configuration).
    :returns: The ``rbac`` roles with their permissions and the
        approval-policy reviewer roles.
    """
    config = runtime.config if runtime is not None else None
    return DevRolesOut.model_validate(dev_role_catalog(config))
