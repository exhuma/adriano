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

**Erratum target titles.** An erratum hit carries the title of the
decision it corrects (``erratum_for_title``). The targets of all
erratum hits of the page are read with **one** query
(:meth:`~app.storage.port.CatalogStore.list_published_by_uuid`) and
resolved with the same rules as the detail page's ``erratum_for``
(:class:`~app.domain.relationships.RelationshipIndex`: published rows,
same project first, ambiguous -> no title). The lookup is total: the
``corrects`` link is selected by type, an unresolved or self-targeting
link simply yields no title. Targets are not restricted to decisions,
so an erratum of an erratum shows the corrected erratum's title, as
its detail page does (where ``erratum_target_is_erratum`` flags it).

Public API: :class:`RecordTypeFilter`, :class:`IssueCounts`,
:class:`CatalogSearchItem`, :class:`CatalogSearchPage`,
:func:`search_records`.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.domain.approval import ApprovalStateCode, Policy
from app.domain.issues import Issue, Severity
from app.domain.relationships import RecordSummary, RelationshipIndex
from app.domain.values import Identity, Links, LinkType, RecordKind
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
    "RecordTypeFilter",
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
    :param erratum_for_title: For an erratum, the title of the
        decision it corrects, when that resolves.
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
    :returns: Title by erratum hit id, for targets that resolve.
    """
    errata = [
        item
        for item in items
        if item.record_kind is RecordKind.ERRATUM and item.corrects
    ]
    targets = store.list_published_by_uuid(
        {item.corrects for item in errata if item.corrects}
    )
    if not targets:
        return {}
    titles = {target.summary.key: target.title for target in targets}
    summaries = {target.summary.key: target.summary for target in targets}
    for item in errata:
        # The hit's own summary carries only its ``corrects`` link, even
        # when the hit is also a target row (an erratum of an erratum,
        # or one whose ``erratum-for`` is its own UUID).
        summaries[str(item.id)] = _hit_summary(item)
    index = RelationshipIndex(summaries.values())
    result: dict[uuid.UUID, str] = {}
    for item in errata:
        link = index.view(str(item.id)).first_link(LinkType.CORRECTS)
        key = None if link is None else link.target_key
        if key is not None and key in titles:
            result[item.id] = titles[key]
    return result


def _hit_summary(item: SearchItem) -> RecordSummary:
    """
    Build the relationship summary of an erratum hit (``corrects`` only).

    :param item: The erratum hit.
    :returns: Its summary, keyed by ``str(item.id)``.
    """
    return RecordSummary(
        key=str(item.id),
        identity=Identity(item.source_id, item.project, item.record_key),
        adr_uuid=item.adr_uuid,
        links=Links(corrects=item.corrects),
        record_kind=RecordKind.ERRATUM,
        path=item.path,
        published=item.kind is RecordState.PUBLISHED,
    )


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
        erratum_for_title=erratum_for_title,
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
    record_type: RecordTypeFilter = RecordTypeFilter.DECISION,
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
    page_result = store.search(query, filters, page, page_size, policy=policy)
    titles = _target_titles(store, page_result.items)
    return CatalogSearchPage(
        items=tuple(
            _search_item(item, titles.get(item.id))
            for item in page_result.items
        ),
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )
