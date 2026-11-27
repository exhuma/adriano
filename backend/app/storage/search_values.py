"""
Value types of the catalog search, crossing the storage port.

Plain frozen dataclasses, independent of any ORM; kept apart from
:mod:`app.storage.values` only to keep modules small. Import them
through :mod:`app.storage.port`, which re-exports them.

Public API: :class:`SearchFilters`, :class:`SearchItem`,
:class:`SearchPage`, :class:`FacetEntry`.
"""

import datetime
import uuid
from dataclasses import dataclass

from app.domain.approval import ApprovalStateCode
from app.domain.issues import Issue
from app.domain.values import RecordKind
from app.storage.values import RecordState


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchFilters:
    """
    Search filters; ``None`` / ``False`` means "no filter".

    :param source_id: Registration id.
    :param project: Project path.
    :param kind: Published or candidate.
    :param needs_approval: Only records whose approval state needs
        approval (:func:`app.domain.approval.evaluate`).
    :param record_kind: Only decisions or only errata.
    """

    source_id: str | None = None
    project: str | None = None
    kind: RecordState | None = None
    needs_approval: bool = False
    record_kind: RecordKind | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchItem:
    """
    One search hit (one row: a published ADR or a candidate).

    :param kind: Published or candidate.
    :param source_id: Registration id.
    :param project: Project path.
    :param path: File path inside the project.
    :param ref: Branch/ref of the content.
    :param adr_uuid: The ADR's UUID.
    :param digest: Current digest.
    :param title: Display title.
    :param record_kind: Decision or erratum.
    :param decision_date: Displayed decision date.
    :param decision_date_inferred: Whether the date is inferred.
    :param issues: Validation issues.
    :param approval_state: Approval state of the current digest, computed
        by the store with the same rules as
        :func:`app.domain.approval.evaluate`.
    :param corrects: UUID an erratum corrects (``None`` for decisions).
    """

    kind: RecordState
    source_id: str
    project: str
    path: str
    ref: str
    adr_uuid: uuid.UUID
    digest: str
    title: str
    record_kind: RecordKind
    decision_date: datetime.date | None
    decision_date_inferred: bool
    issues: tuple[Issue, ...]
    approval_state: ApprovalStateCode
    corrects: uuid.UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchPage:
    """
    One page of search results.

    :param items: Hits on this page.
    :param total: Number of hits over all pages.
    :param page: 1-based page number.
    :param page_size: Requested page size.
    """

    items: tuple[SearchItem, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True, slots=True, kw_only=True)
class FacetEntry:
    """
    ADR count for one ``(source_id, project)`` pair.

    Used to populate the source/project filter select in the UI
    (:meth:`app.storage.port.CatalogStore.list_facets`); counts
    decisions (one per UUID, published or only proposed as a
    candidate), never errata.

    :param source_id: Registration id.
    :param project: Project path.
    :param count: Number of decision UUIDs in this source and project.
    """

    source_id: str
    project: str
    count: int
