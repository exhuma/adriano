"""
``POST /api/v1/records/{id}/decisions``: accept or reject content.

Needs a signed-in caller with ``read``; reviewing itself is decided by
the approval policy, not by a permission. All checks and error codes
live in :mod:`app.services.decisions`; the response is the stored,
append-only event (201) with server-set id and timestamp.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.auth.deps import Principal, require_permission
from app.auth.rbac import Permission
from app.composition import (
    CatalogRuntime,
    get_catalog_runtime,
    get_store_provider,
)
from app.schemas.approval import DecisionIn
from app.schemas.records import DecisionSummaryOut
from app.services.approval_view import decision_summary
from app.services.decisions import Reviewer, record_decision
from app.storage.port import CatalogStoreProvider

router = APIRouter(prefix="/api/v1", tags=["decisions"])

_read = require_permission(Permission.READ)

_ERROR = {"description": "Error body `{detail, code, hint}`."}
_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: _ERROR,
    404: _ERROR,
    409: _ERROR,
}


def reviewer_from(principal: Principal) -> Reviewer:
    """
    Describe an authenticated caller as a (potential) reviewer.

    :param principal: The authenticated caller.
    :returns: The reviewer value used by the services.
    """
    return Reviewer(
        issuer=principal.issuer,
        subject=principal.subject,
        display=principal.display,
        email=principal.email,
        roles=principal.roles,
    )


@router.post(
    "/records/{record_id}/decisions",
    response_model=DecisionSummaryOut,
    status_code=201,
    responses=_RESPONSES,
)
def post_decision(
    record_id: uuid.UUID,
    body: DecisionIn,
    principal: Principal = Depends(_read),
    provider: CatalogStoreProvider = Depends(get_store_provider),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
) -> DecisionSummaryOut:
    """
    Record an accept/reject decision for the record's current digest.

    :param record_id: Record id.
    :param body: Action, optional comment and expected digest.
    :param principal: The authenticated caller (``read`` required).
    :param provider: Storage provider (overridden by tests).
    :param runtime: Startup configuration state (approval policy).
    :returns: The stored event.
    """
    event = record_decision(
        provider,
        record_id,
        action=body.action,
        comment=body.comment,
        expected_digest=body.expected_digest,
        reviewer=reviewer_from(principal),
        policy_config=runtime.config.policy if runtime is not None else None,
    )
    return DecisionSummaryOut.model_validate(
        decision_summary(event, event.digest)
    )
