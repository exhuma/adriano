"""
Dev-only token endpoint: ``POST /auth/dev/token``.

**Never enabled in production.** :func:`app.main.create_app` imports and
mounts this router only when ``ADRIANO_DEV_AUTH_ENABLED`` is true *and*
``ADRIANO_DEV_SHARED_SECRET`` is set, so the path is a plain 404
otherwise. It mints an HS256 token (:func:`app.auth.dev.mint_dev_token`)
for any requested identity -- that is the point of a dev login.
"""

from fastapi import APIRouter, Depends

from app.auth.dev import DEFAULT_MINUTES, DevIdentity, mint_dev_token
from app.config import Settings, get_settings
from app.errors import AuthUnavailableError
from app.schemas.auth import DevTokenIn, DevTokenOut

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
