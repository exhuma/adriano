"""
HTTP routes for searching and viewing catalog records.

Thin: query-parameter validation and status codes only; all assembly
logic lives in :mod:`app.services.catalog`. These routes only use the
storage provider (:func:`app.composition.get_store_provider`) and the
catalog configuration loaded at startup
(:func:`app.composition.get_catalog_runtime`) -- never a source
adapter, so normal browse/search requests make no source calls (see
``phases/DECISIONS.md``, "HTTP API").
"""

import datetime
import uuid

from fastapi import APIRouter, Depends, Query

from app.auth.deps import require_permission
from app.auth.rbac import Permission
from app.composition import (
    CatalogRuntime,
    get_catalog_runtime,
    get_store_provider,
)
from app.config import Settings, get_settings
from app.domain.approval import Policy, PolicyStatus
from app.errors import NotFoundError
from app.schemas.records import RecordDetailOut, SearchPageOut
from app.services import catalog
from app.storage.port import MAX_PAGE_SIZE, CatalogStoreProvider, RecordState

router = APIRouter(
    prefix="/api/v1",
    tags=["records"],
    dependencies=[Depends(require_permission(Permission.READ))],
)

_DEFAULT_PAGE_SIZE = 20


def _policy(
    runtime: CatalogRuntime | None,
) -> tuple[Policy | None, PolicyStatus]:
    """
    Read the configured approval policy and its status from the runtime.

    :param runtime: Startup state; ``None`` only when the application
        lifespan did not run (not possible for a real request).
    :returns: The policy (``None`` if missing or invalid) and its
        configuration status.
    """
    if runtime is None:
        return None, PolicyStatus.MISSING
    return runtime.config.policy.policy, runtime.config.policy.status


@router.get("/records", response_model=SearchPageOut)
def list_records(
    q: str | None = Query(default=None, description="Free text search."),
    source: str | None = Query(default=None, description="Registration id."),
    project: str | None = Query(default=None, description="Project path."),
    state: RecordState | None = Query(default=None, description="state"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    provider: CatalogStoreProvider = Depends(get_store_provider),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
) -> SearchPageOut:
    """
    Search the catalog with the Phase 1 filters.

    The ``needs_approval`` filter is not available yet; it arrives in
    phase 07 together with the decision/approval actions.

    :param q: Free text (titles, bodies, UUIDs, paths); blank or
        omitted matches everything.
    :param source: Restrict to one registration id.
    :param project: Restrict to one project path.
    :param state: Restrict to ``published`` or ``candidate``.
    :param page: 1-based page number.
    :param page_size: Page size, 1 to :data:`~app.storage.port.MAX_PAGE_SIZE`.
    :param provider: Storage provider (overridden by tests).
    :param runtime: Startup configuration state.
    :returns: The page.
    """
    policy, _status = _policy(runtime)
    with provider.unit_of_work() as store:
        page_result = catalog.search_records(
            store,
            query=q,
            source_id=source,
            project=project,
            kind=state,
            page=page,
            page_size=page_size,
            policy=policy,
        )
    return SearchPageOut.model_validate(page_result)


@router.get("/records/{record_id}", response_model=RecordDetailOut)
def get_record(
    record_id: uuid.UUID,
    provider: CatalogStoreProvider = Depends(get_store_provider),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
    settings: Settings = Depends(get_settings),
) -> RecordDetailOut:
    """
    Fetch one record's detail page.

    Decision history is included (read-only); recording a new decision
    arrives in phase 07.

    :param record_id: Record id.
    :param provider: Storage provider (overridden by tests).
    :param runtime: Startup configuration state.
    :param settings: Application settings (for the stale threshold).
    :returns: The detail.
    :raises app.errors.NotFoundError: If the record does not exist.
    """
    policy, policy_status = _policy(runtime)
    with provider.unit_of_work() as store:
        detail = catalog.get_record_detail(
            store,
            record_id,
            policy=policy,
            policy_status=policy_status,
            now=datetime.datetime.now(datetime.UTC),
            stale_after_minutes=settings.stale_after_minutes,
        )
    if detail is None:
        raise NotFoundError(f"record {record_id} not found")
    return RecordDetailOut.model_validate(detail)
