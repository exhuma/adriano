"""
Dev-only endpoints: ``POST /auth/dev/token`` and ``GET /auth/dev/roles``.

**Never enabled in production.** :func:`app.main.create_app` imports and
mounts this router only when ``ADRIANO_DEV_AUTH_ENABLED`` is true *and*
``ADRIANO_DEV_SHARED_SECRET`` is set, so the path is a plain 404
otherwise. It mints an HS256 token (:func:`app.auth.dev.mint_dev_token`)
for any requested identity -- that is the point of a dev login.
``GET /auth/dev/roles`` lists the loaded catalog's role names so the
dev sign-in dialog can offer presets that match this catalog.
"""

from fastapi import APIRouter, Depends

from app.auth.dev import DEFAULT_MINUTES, DevIdentity, mint_dev_token
from app.composition import CatalogRuntime, get_catalog_runtime
from app.config import Settings, get_settings
from app.errors import AuthUnavailableError
from app.schemas.auth import DevRolesOut, DevTokenIn, DevTokenOut
from app.services.dev_roles import dev_role_catalog

router = APIRouter(prefix="/auth/dev", tags=["dev-auth"])


@router.post("/token", response_model=DevTokenOut)
def create_dev_token(
    body: DevTokenIn, settings: Settings = Depends(get_settings)
) -> DevTokenOut:
    """
    Mint a dev access token for the requested identity.

    :param body: Subject, name, email and roles.
    :param settings: Application settings.
    :returns: The token and its lifetime in seconds.
    :raises AuthUnavailableError: If the shared secret is not set.
    """
    if not settings.dev_shared_secret:
        raise AuthUnavailableError(
            "dev auth has no ADRIANO_DEV_SHARED_SECRET",
            code="auth_unconfigured",
        )
    identity = DevIdentity(
        sub=body.sub, name=body.name, email=body.email, roles=body.roles
    )
    token = mint_dev_token(settings, identity, minutes=DEFAULT_MINUTES)
    return DevTokenOut(access_token=token, expires_in=DEFAULT_MINUTES * 60)


@router.get("/roles", response_model=DevRolesOut)
def list_dev_roles(
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
) -> DevRolesOut:
    """
    List the role names of the loaded catalog for dev sign-in presets.

    Unauthenticated like the token route: the dev dialog calls it
    before anyone is signed in. It exposes role names and permissions
    only, never reviewer users.

    :param runtime: Startup state (loaded configuration).
    :returns: The ``rbac`` roles with their permissions and the
        approval-policy reviewer roles.
    """
    config = runtime.config if runtime is not None else None
    return DevRolesOut.model_validate(dev_role_catalog(config))
