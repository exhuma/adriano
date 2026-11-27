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

**Record type.** :class:`RecordTypeFilter` selects decisions (the
default), errata, or both; it is pushed into SQL like every other
filter and combines with them (including ``needs_approval``).

**Sort order.** :func:`resolve_sort` owns the default: ``relevance``
when a non-blank query is set, otherwise ``title``; an explicit
``relevance`` without a query falls back to ``title`` (there is no
rank to order by). ``recent`` orders by ``record.updated_at``, which
moves only when the content digest changes (``last_seen_at`` is the
poll heartbeat), newest first. Every order ends with title and the
row key (UUID, state, ref), so pages are stable.

**One hit per ADR.** A hit is the row the catalog shows for the ADR:
its published row, else its most recently updated candidate (see
:mod:`app.storage.postgres.search`). ``adr_uuid`` addresses the ADR
(``/records/{uuid}``); ``kind`` and ``ref`` say which row the hit
is. The ``state`` filter selects the row kind instead (``candidate``:
the newest candidate of every ADR). The query and the other filters
apply to that one row.

**Erratum target titles.** An erratum hit carries the title of the
decision it corrects (``erratum_for_title``). The targets of all
erratum hits of the page are read with **one** query
(:meth:`~app.storage.port.CatalogStore.published_titles`) and resolve
like the detail page's ``erratum_for``: the published ADR with that
UUID; a missing or self-targeting link simply yields no title.
Targets are not restricted to decisions, so an erratum of an erratum
shows the corrected erratum's title, as its detail page does (where
``erratum_target_is_erratum`` flags it).

Public API: :class:`RecordTypeFilter`, :class:`IssueCounts`,
:class:`CatalogSearchItem`, :class:`CatalogSearchPage`,
:func:`resolve_sort`, :func:`search_records`.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.domain.approval import ApprovalStateCode, Policy
from app.domain.issues import Issue, Severity
from app.domain.values import RecordKind
from app.services.approval_view import is_approvable
from app.storage.port import (
    CatalogStore,
    RecordState,
    SearchFilters,
    SearchItem,
    SearchSort,
)

__all__ = [
    "CatalogSearchItem",
    "CatalogSearchPage",
    "IssueCounts",
    "RecordTypeFilter",
    "resolve_sort",
    "search_records",
]


class RecordTypeFilter(StrEnum):
    """Which record kinds a search returns."""

    DECISION = "decision"
    ERRATUM = "erratum"
    ALL = "all"


_RECORD_KIND = {
    RecordTypeFilter.DECISION: RecordKind.DECISION,
    RecordTypeFilter.ERRATUM: RecordKind.ERRATUM,
    RecordTypeFilter.ALL: None,
}


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

    :param adr_uuid: The ADR's UUID (with :attr:`kind` and :attr:`ref`,
        the row key).
    :param title: Display title.
    :param source_id: Registration id.
    :param project: Project path.
    :param path: File path inside the project.
    :param ref: Branch/ref of the content.
    :param kind: Published or candidate.
    :param record_kind: Decision or erratum.
    :param approval_state: Approval state of the current digest.
    :param approvable: Whether the content can be decided at all (same
        rule as the record detail,
        :func:`app.services.approval_view.is_approvable`).
    :param issue_counts: Stored validation issue counts.
    :param erratum_for_title: For an erratum, the title of the
        decision it corrects, when that resolves.
    """

    adr_uuid: uuid.UUID
    title: str
    source_id: str
    project: str
    path: str
    ref: str
    kind: RecordState
    record_kind: RecordKind
    approval_state: ApprovalStateCode
    approvable: bool
    issue_counts: IssueCounts
    erratum_for_title: str | None


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


def _target_titles(
    store: CatalogStore, items: Sequence[SearchItem]
) -> dict[uuid.UUID, str]:
    """
    Resolve the corrected decision's title of every erratum hit.

    :param store: Store of the caller's unit of work.
    :param items: Hits of one page.
    :returns: Title by target UUID, for targets that resolve.
    """
    targets = {
        item.corrects
        for item in items
        if item.record_kind is RecordKind.ERRATUM and item.corrects
    }
    return store.published_titles(targets)


def _erratum_title(
    item: SearchItem, titles: dict[uuid.UUID, str]
) -> str | None:
    """
    Pick the corrected record's title of an erratum hit.

    :param item: The hit.
    :param titles: Titles by target UUID (:func:`_target_titles`).
    :returns: The title, or ``None`` for a decision, a missing target or
        an erratum targeting itself.
    """
    if item.record_kind is not RecordKind.ERRATUM or item.corrects is None:
        return None
    if item.corrects == item.adr_uuid:
        return None
    return titles.get(item.corrects)


def _search_item(
    item: SearchItem, erratum_for_title: str | None
) -> CatalogSearchItem:
    """
    Convert one storage search hit to the service value.

    :param item: The storage hit.
    :param erratum_for_title: Resolved target title of an erratum.
    :returns: The search result row.
    """
    return CatalogSearchItem(
        adr_uuid=item.adr_uuid,
        title=item.title,
        source_id=item.source_id,
        project=item.project,
        path=item.path,
        ref=item.ref,
        kind=item.kind,
        record_kind=item.record_kind,
        approval_state=item.approval_state,
        approvable=is_approvable(item),
        issue_counts=_issue_counts(item.issues),
        erratum_for_title=erratum_for_title,
    )


def resolve_sort(sort: SearchSort | None, query: str | None) -> SearchSort:
    """
    Apply the default sort and the no-query fallback.

    :param sort: Requested order, or ``None`` for the default.
    :param query: Free text, or ``None``/blank.
    :returns: ``relevance`` or ``title`` by default (with / without a
        non-blank query); ``title`` for ``relevance`` without a query;
        otherwise *sort* itself.
    """
    has_query = bool((query or "").strip())
    if sort is None:
        return SearchSort.RELEVANCE if has_query else SearchSort.TITLE
    if sort is SearchSort.RELEVANCE and not has_query:
        return SearchSort.TITLE
    return sort


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
    record_type: RecordTypeFilter = RecordTypeFilter.DECISION,
    sort: SearchSort | None = None,
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
    :param record_type: Decisions (default), errata, or both.
    :param sort: Result order, or ``None`` for the default (see
        :func:`resolve_sort`).
    :returns: The page.
    :raises ValueError: If *page* or *page_size* is out of bounds.
    """
    filters = SearchFilters(
        source_id=source_id,
        project=project,
        kind=kind,
        needs_approval=needs_approval,
        record_kind=_RECORD_KIND[record_type],
    )
    page_result = store.search(
        query,
        filters,
        page,
        page_size,
        policy=policy,
        sort=resolve_sort(sort, query),
    )
    titles = _target_titles(store, page_result.items)
    return CatalogSearchPage(
        items=tuple(
            _search_item(item, _erratum_title(item, titles))
            for item in page_result.items
        ),
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )
