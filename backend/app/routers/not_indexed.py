"""
HTTP routes of the not-indexed list (documents intake cannot index).

Both routes need ``read`` (every signed-in user). The list is
read-only: entries are cleared only by intake, never by hand.

- ``GET /not-indexed``: a page, newest ``last_seen_at`` first,
  filterable by ``source_id``, ``project``, ``reason`` (an issue code)
  and ``origin`` (``poll`` or ``push``).
- ``GET /not-indexed/entry``: one entry with its rejected content. A
  location is ``(source_id, project, path, ref)`` and project, path
  and ref contain slashes, so the location is passed as four required
  query parameters (not as path segments).
"""

from fastapi import APIRouter, Depends, Query

from app.auth.deps import require_permission
from app.auth.rbac import Permission
from app.composition import get_store_provider
from app.domain.issues import IssueCode
from app.errors import NotFoundError
from app.schemas.not_indexed import NotIndexedDetailOut, NotIndexedPageOut
from app.services import not_indexed_view
from app.storage.port import (
    MAX_PAGE_SIZE,
    CatalogStoreProvider,
    IntakeKind,
    NotIndexedFilters,
    NotIndexedKey,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["not-indexed"],
    dependencies=[Depends(require_permission(Permission.READ))],
)

_DEFAULT_PAGE_SIZE = 20


@router.get("/not-indexed", response_model=NotIndexedPageOut)
def list_not_indexed(
    source_id: str | None = Query(default=None, description="Registration."),
    project: str | None = Query(default=None, description="Project path."),
    reason: IssueCode | None = Query(
        default=None, description="Only entries carrying this reason code."
    ),
    origin: IntakeKind | None = Query(
        default=None, description="Only entries found by `poll` or `push`."
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    provider: CatalogStoreProvider = Depends(get_store_provider),
) -> NotIndexedPageOut:
    """
    List the documents intake could not index, newest first.

    :param source_id: Restrict to one registration.
    :param project: Restrict to one project path.
    :param reason: Restrict to entries carrying this reason code.
    :param origin: Restrict to one intake.
    :param page: 1-based page number.
    :param page_size: Page size, 1 to :data:`~app.storage.port.
        MAX_PAGE_SIZE`.
    :param provider: Storage provider (overridden by tests).
    :returns: The page.
    """
    filters = NotIndexedFilters(
        source_id=source_id, project=project, reason=reason, origin=origin
    )
    with provider.unit_of_work() as store:
        result = not_indexed_view.list_not_indexed(
            store, filters, page, page_size
        )
    return NotIndexedPageOut.model_validate(result)


@router.get("/not-indexed/entry", response_model=NotIndexedDetailOut)
def get_not_indexed_entry(
    source_id: str = Query(description="Registration id of the location."),
    project: str = Query(description="Project path of the location."),
    path: str = Query(description="File path of the location."),
    ref: str = Query(description="Ref of the location."),
    provider: CatalogStoreProvider = Depends(get_store_provider),
) -> NotIndexedDetailOut:
    """
    Fetch one entry with the content intake rejected.

    :param source_id: Registration id of the location.
    :param project: Project path of the location.
    :param path: File path of the location.
    :param ref: Ref of the location.
    :param provider: Storage provider (overridden by tests).
    :returns: The entry; ``content`` is ``null`` when it could not be
        read.
    :raises app.errors.NotFoundError: If the location has no entry (it
        may have been cleared since the list was read).
    """
    key = NotIndexedKey(source_id, project, path, ref)
    with provider.unit_of_work() as store:
        detail = not_indexed_view.get_not_indexed_detail(store, key)
    if detail is None:
        raise NotFoundError(
            "no not-indexed entry at this location",
            code="not_indexed_not_found",
        )
    return NotIndexedDetailOut.model_validate(detail)
