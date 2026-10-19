"""
Read-only catalog search.

Takes a :class:`~app.storage.port.CatalogStore` (already inside a unit
of work opened by the caller) plus plain values, and returns plain
dataclasses; nothing here imports FastAPI or a source adapter. Routers
convert the results with ``SomeSchema.model_validate(value)`` (the
schemas declare ``from_attributes=True``).

**Derived status on search results.** Search list items do not carry
the relationship-derived display status: computing it would require
building the full relationship index
(:mod:`app.services.record_relationships`) on every search request. It
is only available on the detail endpoint. Documented as an open item
for the frontend and for phase 09.

Public API: :class:`IssueCounts`, :class:`CatalogSearchItem`,
:class:`CatalogSearchPage`, :func:`search_records`.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.approval import ApprovalStateCode, Policy
from app.domain.issues import Issue, Severity
from app.domain.values import RecordKind
from app.storage.port import (
    CatalogStore,
    RecordState,
    SearchFilters,
    SearchItem,
)

__all__ = [
    "CatalogSearchItem",
    "CatalogSearchPage",
    "IssueCounts",
    "search_records",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class IssueCounts:
    """
    Stored-issue counts of one record, by severity.

    :param error: Number of error-severity issues.
    :param warning: Number of warning-severity issues.
    """

    error: int
    warning: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogSearchItem:
    """
    One search result row.

    :param id: Record id.
    :param title: Display title.
    :param source_id: Registration id.
    :param project: Project path.
    :param path: File path inside the project.
    :param ref: Branch/ref of the content.
    :param kind: Published or candidate.
    :param record_kind: Decision or erratum.
    :param approval_state: Approval state of the current digest.
    :param issue_counts: Stored validation issue counts.
    """

    id: uuid.UUID
    title: str
    source_id: str
    project: str
    path: str
    ref: str
    kind: RecordState
    record_kind: RecordKind
    approval_state: ApprovalStateCode
    issue_counts: IssueCounts


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogSearchPage:
    """
    One page of search results.

    :param items: Hits on this page.
    :param total: Number of hits over all pages.
    :param page: 1-based page number.
    :param page_size: Requested page size.
    """

    items: tuple[CatalogSearchItem, ...]
    total: int
    page: int
    page_size: int


def _issue_counts(issues: Iterable[Issue]) -> IssueCounts:
    """
    Count stored issues by severity.

    :param issues: The record's stored issues.
    :returns: The counts.
    """
    issues = tuple(issues)
    return IssueCounts(
        error=sum(1 for i in issues if i.severity is Severity.ERROR),
        warning=sum(1 for i in issues if i.severity is Severity.WARNING),
    )


def _search_item(item: SearchItem) -> CatalogSearchItem:
    """
    Convert one storage search hit to the service value.

    :param item: The storage hit.
    :returns: The search result row.
    """
    return CatalogSearchItem(
        id=item.id,
        title=item.title,
        source_id=item.source_id,
        project=item.project,
        path=item.path,
        ref=item.ref,
        kind=item.kind,
        record_kind=item.record_kind,
        approval_state=item.approval_state,
        issue_counts=_issue_counts(item.issues),
    )


def search_records(
    store: CatalogStore,
    *,
    query: str | None,
    source_id: str | None,
    project: str | None,
    kind: RecordState | None,
    page: int,
    page_size: int,
    policy: Policy | None,
    needs_approval: bool = False,
) -> CatalogSearchPage:
    """
    Search the catalog with the Phase 1 filters.

    :param store: Store of the caller's unit of work.
    :param query: Free text, or ``None``/blank for all records.
    :param source_id: Restrict to one registration, or ``None``.
    :param project: Restrict to one project, or ``None``.
    :param kind: Restrict to published or candidate, or ``None``.
    :param page: 1-based page number.
    :param page_size: Page size, 1 to :data:`~app.storage.port.MAX_PAGE_SIZE`.
    :param policy: The configured policy, or ``None``.
    :param needs_approval: Only records whose current content does not
        satisfy the policy (pending, rejected, changed since acceptance,
        policy missing); evaluated in SQL by the store.
    :returns: The page.
    :raises ValueError: If *page* or *page_size* is out of bounds.
    """
    filters = SearchFilters(
        source_id=source_id,
        project=project,
        kind=kind,
        needs_approval=needs_approval,
    )
    page_result = store.search(query, filters, page, page_size, policy=policy)
    return CatalogSearchPage(
        items=tuple(_search_item(item) for item in page_result.items),
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )
