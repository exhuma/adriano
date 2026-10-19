"""
``GET /api/v1/me``: caller identity, permissions, reviewer eligibility.

Needs authentication only (no permission), so a signed-in user without
any role can still see why they cannot browse.
"""

from fastapi import APIRouter, Depends

from app.auth.deps import Principal, get_permissions, get_principal
from app.auth.rbac import Permission, reviewer_eligibility
from app.composition import CatalogRuntime, get_catalog_runtime
from app.schemas.auth import MeOut, ReviewerOut

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me", response_model=MeOut)
def get_me(
    principal: Principal = Depends(get_principal),
    permissions: frozenset[Permission] = Depends(get_permissions),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
) -> MeOut:
    """
    Describe the caller.

    :param principal: The authenticated caller.
    :param permissions: The caller's permissions.
    :param runtime: Startup state (approval policy).
    :returns: Identity, permissions and reviewer eligibility.
    """
    policy = runtime.config.policy if runtime is not None else None
    reviewer = reviewer_eligibility(
        policy,
        issuer=principal.issuer,
        subject=principal.subject,
        roles=principal.roles,
    )
    return MeOut(
        issuer=principal.issuer,
        subject=principal.subject,
        display=principal.display,
        email=principal.email,
        roles=list(principal.roles),
        permissions=sorted(permissions),
        reviewer=ReviewerOut.model_validate(reviewer),
    )
