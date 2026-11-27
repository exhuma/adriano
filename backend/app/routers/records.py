"""
HTTP routes for searching and viewing catalog records.

**Addressing.** An ADR is its authored UUID, globally unique:

- ``GET /records/{uuid}``: the ADR's published row, or, without one,
  its most recently updated candidate;
- ``GET /records/{uuid}/candidates/{ref}``: the candidate read from
  *ref* (also the published row when it was read from that ref). A
  ref is a git ref and may contain slashes (``feature/x``), so it is
  matched with a ``path`` converter, which must be the last segment of
  the URL; clients percent-encode nothing but ``%`` and ``?``/``#``;
- ``GET /records/{uuid}/diff`` and ``POST /records/{uuid}/decisions``
  cannot end in a ref, so they take it as the optional ``ref`` query
  parameter instead (omitted: the same row as the first route).

Thin: query-parameter validation and status codes only; all assembly
logic lives in :mod:`app.services.search` and
:mod:`app.services.record_detail`. These routes only use the
storage provider (:func:`app.composition.get_store_provider`) and the
catalog configuration loaded at startup
(:func:`app.composition.get_catalog_runtime`) -- never a source
adapter, so normal browse/search requests make no source calls (see
``docs/developer/decisions/0004-reads-from-local-index.rst``).
"""

import datetime
import uuid

from fastapi import APIRouter, Depends, Query

from app.auth.deps import Principal, require_permission
from app.auth.rbac import Permission
from app.composition import (
    CatalogRuntime,
    get_catalog_runtime,
    get_store_provider,
)
from app.config import Settings, get_settings
from app.domain.approval import Policy, PolicyStatus
from app.errors import NotFoundError
from app.routers.decisions import reviewer_from
from app.schemas.records import RecordDetailOut, RecordDiffOut, SearchPageOut
from app.services import record_detail, search
from app.services.diff import diff_record
from app.storage.port import (
    MAX_PAGE_SIZE,
    CatalogStoreProvider,
    RecordState,
    SearchSort,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["records"],
    dependencies=[Depends(require_permission(Permission.READ))],
)

_DEFAULT_PAGE_SIZE = 20
_REF = (
    "Ref of a candidate; omitted: the published row (or, without one, "
    "the newest candidate)."
)
_read = require_permission(Permission.READ)


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
    needs_approval: bool = Query(
        default=False,
        description=(
            "Only records whose current content does not satisfy the "
            "policy: pending, rejected, changed since acceptance, or "
            "policy missing."
        ),
    ),
    record_type: search.RecordTypeFilter = Query(
        default=search.RecordTypeFilter.DECISION,
        description=(
            "Which records to return: `decision` (default), `erratum`, "
            "or `all`. Combines with every other filter."
        ),
    ),
    sort: SearchSort | None = Query(
        default=None,
        description=(
            "Result order: `relevance` (text rank, best first), `title` "
            "(A-Z) or `recent` (content last changed, newest first). "
            "Default: `relevance` when `q` is set, else `title`; "
            "`relevance` without `q` falls back to `title`. Ties are "
            "broken by title, then UUID, state and ref."
        ),
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    provider: CatalogStoreProvider = Depends(get_store_provider),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
) -> SearchPageOut:
    """
    Search the catalog with the Phase 1 filters.

    :param q: Free text (titles, bodies, UUIDs, paths); blank or
        omitted matches everything.
    :param source: Restrict to one registration id.
    :param project: Restrict to one project path.
    :param state: Restrict to ``published`` or ``candidate``.
    :param needs_approval: Restrict to records that need approval.
    :param record_type: Decisions (default), errata, or both.
    :param sort: Result order, or omitted for the default.
    :param page: 1-based page number.
    :param page_size: Page size, 1 to :data:`~app.storage.port.MAX_PAGE_SIZE`.
    :param provider: Storage provider (overridden by tests).
    :param runtime: Startup configuration state.
    :returns: The page.
    """
    policy, _status = _policy(runtime)
    with provider.unit_of_work() as store:
        page_result = search.search_records(
            store,
            query=q,
            source_id=source,
            project=project,
            kind=state,
            page=page,
            page_size=page_size,
            policy=policy,
            needs_approval=needs_approval,
            record_type=record_type,
            sort=sort,
        )
    return SearchPageOut.model_validate(page_result)


def _detail(
    adr_uuid: uuid.UUID,
    ref: str | None,
    provider: CatalogStoreProvider,
    runtime: CatalogRuntime | None,
    settings: Settings,
    principal: Principal,
) -> RecordDetailOut:
    """
    Assemble the detail of one row of an ADR.

    :param adr_uuid: The ADR's UUID.
    :param ref: A candidate's ref; ``None`` for the default row.
    :param provider: Storage provider.
    :param runtime: Startup configuration state.
    :param settings: Application settings.
    :param principal: The authenticated caller.
    :returns: The detail.
    :raises app.errors.NotFoundError: If the row does not exist.
    """
    policy, policy_status = _policy(runtime)
    with provider.unit_of_work() as store:
        detail = record_detail.get_record_detail(
            store,
            adr_uuid,
            ref=ref,
            policy=policy,
            policy_status=policy_status,
            now=datetime.datetime.now(datetime.UTC),
            stale_after_minutes=settings.stale_after_minutes,
            reviewer=reviewer_from(principal),
            config_sources=runtime.config.sources if runtime else (),
        )
    if detail is None:
        where = f" at ref {ref!r}" if ref is not None else ""
        raise NotFoundError(
            f"record {adr_uuid}{where} not found", code="record_not_found"
        )
    return RecordDetailOut.model_validate(detail)


@router.get("/records/{adr_uuid}", response_model=RecordDetailOut)
def get_record(
    adr_uuid: uuid.UUID,
    provider: CatalogStoreProvider = Depends(get_store_provider),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
    settings: Settings = Depends(get_settings),
    principal: Principal = Depends(_read),
) -> RecordDetailOut:
    """
    Fetch an ADR's detail page.

    Shows the published row, else the newest candidate.

    ``approval.can_decide`` (and the blocked reason) is evaluated for
    the caller.

    :param adr_uuid: The ADR UUID.
    :param provider: Storage provider (overridden by tests).
    :param runtime: Startup configuration state.
    :param settings: Application settings (for the stale threshold).
    :param principal: The authenticated caller.
    :returns: The detail.
    :raises app.errors.NotFoundError: If the record does not exist.
    """
    return _detail(adr_uuid, None, provider, runtime, settings, principal)


@router.get(
    "/records/{adr_uuid}/candidates/{ref:path}",
    response_model=RecordDetailOut,
)
def get_candidate(
    adr_uuid: uuid.UUID,
    ref: str,
    provider: CatalogStoreProvider = Depends(get_store_provider),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
    settings: Settings = Depends(get_settings),
    principal: Principal = Depends(_read),
) -> RecordDetailOut:
    """
    Fetch the detail page of the candidate of an ADR read from *ref*.

    :param adr_uuid: The ADR UUID.
    :param ref: The candidate's git ref; may contain slashes.
    :param provider: Storage provider (overridden by tests).
    :param runtime: Startup configuration state.
    :param settings: Application settings (for the stale threshold).
    :param principal: The authenticated caller.
    :returns: The detail.
    :raises app.errors.NotFoundError: If there is no row at *ref*.
    """
    return _detail(adr_uuid, ref, provider, runtime, settings, principal)


@router.get("/records/{adr_uuid}/diff", response_model=RecordDiffOut)
def get_record_diff(
    adr_uuid: uuid.UUID,
    ref: str | None = Query(default=None, max_length=255, description=_REF),
    from_digest: str | None = Query(
        default=None,
        alias="from",
        max_length=200,
        description="Base digest; default: last decided snapshot, else "
        "the previous revision.",
    ),
    to_digest: str | None = Query(
        default=None,
        alias="to",
        max_length=200,
        description="Target digest; default: the current digest.",
    ),
    provider: CatalogStoreProvider = Depends(get_store_provider),
) -> RecordDiffOut:
    """
    Diff two stored snapshots of the record's ADR.

    Only digests related to the record are accepted (404
    ``unknown_revision`` otherwise); see :mod:`app.services.diff`.

    :param adr_uuid: The ADR UUID.
    :param ref: A candidate's ref; omitted for the published row.
    :param from_digest: Base digest (query ``from``).
    :param to_digest: Target digest (query ``to``).
    :param provider: Storage provider (overridden by tests).
    :returns: The diff, or ``base: null`` with ``reason:
        "no_prior_revision"``.
    """
    with provider.unit_of_work() as store:
        diff = diff_record(
            store,
            adr_uuid,
            ref=ref,
            from_digest=from_digest,
            to_digest=to_digest,
        )
    return RecordDiffOut.model_validate(diff)
