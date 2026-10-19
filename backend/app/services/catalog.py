"""
Read-only catalog service: search, record detail, sources and facets.

Every function here takes a :class:`~app.storage.port.CatalogStore`
(already inside a unit of work opened by the caller) plus plain values,
and returns plain dataclasses; nothing here imports FastAPI or a source
adapter. Routers convert the returned dataclasses to response models
with ``SomeSchema.model_validate(value)`` (the schemas declare
``from_attributes=True``).

Design decisions worth recording for later phases:

- **Candidate participation in relationships.** A
  :class:`~app.domain.relationships.RelationshipIndex` is built from the
  published rows (:meth:`~app.storage.port.CatalogStore.
  list_relationship_summaries`) plus the identity siblings of the record
  whose detail is requested (:meth:`~app.storage.port.CatalogStore.
  list_identity_siblings`, which always includes the queried record
  itself, published or candidate). A candidate's outbound links
  therefore resolve against published rows and its own identity's other
  rows only; links authored by *other* candidates (of a different
  identity) are never resolved against anything. This also means
  ``duplicate_uuid`` detection for a candidate's detail view does not
  see duplicates held only by unrelated candidates. Revisit if a later
  phase needs candidates to participate more broadly.
- **Cost of the detail endpoint.** Building the published-row
  relationship index is one query over every published row, run again
  on every detail request; at the catalog sizes planned for Phase 1
  benchmarking (~20k records) this is not optimised further here
  (no caching, no incremental index). Flagged as a phase 09 performance
  item rather than solved prematurely, per the phase 05 task brief.
  Looking up the title of every related record is one query per related
  id (never per catalog row), so it stays bounded by the small number of
  links a record has, not by catalog size.
- **Derived status on search results.** Search list items do not carry
  the relationship-derived display status: computing it would require
  building the same full relationship index on every search request.
  It is only available on the detail endpoint. Documented as an open
  item for the frontend and for phase 09.
"""

import datetime
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.domain import fields as domain_fields
from app.domain.approval import (
    ApprovalStateCode,
    DecisionEventView,
    Policy,
    PolicyStatus,
    evaluate,
)
from app.domain.issues import Issue, Severity
from app.domain.relationships import (
    DisplayStatus,
    InboundLink,
    InboundType,
    RecordSummary,
    RelationshipIndex,
    RelationshipView,
    Resolution,
    ResolvedLink,
)
from app.domain.values import LinkType, RecordKind, TitleSource
from app.services.approval_view import (
    ApprovalSummary,
    CompetingCandidate,
    DecisionProvenance,
    DecisionSummary,
    DivergenceInfo,
    PolicySummary,
    build_approval,
    is_approvable,
)
from app.services.decisions import Reviewer
from app.services.sources_view import is_stale
from app.storage.port import (
    CatalogStore,
    JsonObject,
    PollStatus,
    RecordState,
    Registration,
    SearchFilters,
    SearchItem,
    StoredRecord,
)

__all__ = [
    "ApprovalSummary",
    "CatalogSearchItem",
    "CatalogSearchPage",
    "CompetingCandidate",
    "DecisionProvenance",
    "DecisionSummary",
    "DivergenceInfo",
    "ErratumInfo",
    "InboundLinkInfo",
    "IssueCounts",
    "OutboundLinkInfo",
    "PolicySummary",
    "RecordDetail",
    "RecordFreshness",
    "RecordMetadata",
    "RecordProvenance",
    "SiblingInfo",
    "get_record_detail",
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


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordMetadata:
    """
    Identity and authored metadata of one record.

    :param id: Record id.
    :param adr_uuid: Authored UUID, if valid.
    :param decision_date: Displayed decision date.
    :param decision_date_inferred: Whether the date is only inferred
        from the filename.
    :param kind: Published or candidate.
    :param record_kind: Decision or erratum.
    :param title: Display title.
    :param title_source: Where the title came from.
    :param digest: Canonical digest of the current content.
    :param previous_digest: Digest before the latest content change.
    """

    id: uuid.UUID
    adr_uuid: uuid.UUID | None
    decision_date: datetime.date | None
    decision_date_inferred: bool
    kind: RecordState
    record_kind: RecordKind
    title: str
    title_source: TitleSource
    digest: str
    previous_digest: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordProvenance:
    """
    Where a record's content came from.

    :param source_id: Registration id.
    :param project: Project path.
    :param path: File path inside the project.
    :param ref: Branch/ref the content came from.
    :param source_url: Link to the content at the source, if any.
    """

    source_id: str
    project: str
    path: str
    ref: str
    source_url: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordFreshness:
    """
    Freshness of a record's owning registration.

    :param last_attempt_at: Start of the registration's latest poll
        attempt.
    :param last_success_at: Start of its latest fully successful poll.
    :param last_status: Outcome of its latest poll.
    :param stale: Whether the indexed content may not reflect the
        current published source (see :func:`is_stale`).
    """

    last_attempt_at: datetime.datetime | None
    last_success_at: datetime.datetime | None
    last_status: PollStatus
    stale: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class OutboundLinkInfo:
    """
    One outbound link and how it resolved.

    :param link_type: The authored relationship.
    :param target_uuid: The authored target UUID.
    :param target_id: Resolved target record id, or ``None`` if
        unresolved.
    :param target_title: Resolved target title, or ``None``.
    :param resolution: Tier used, or ``None`` when unresolved.
    :param ambiguous: Whether several targets matched equally well.
    :param candidate_ids: Ids of the equally good targets when
        ambiguous.
    """

    link_type: LinkType
    target_uuid: uuid.UUID
    target_id: uuid.UUID | None
    target_title: str | None
    resolution: Resolution | None
    ambiguous: bool
    candidate_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class InboundLinkInfo:
    """
    A link from another record to the one being viewed.

    :param link_type: ``updated_by`` or ``obsoleted_by``.
    :param source_id: Id of the linking record.
    :param source_title: Title of the linking record.
    """

    link_type: InboundType
    source_id: uuid.UUID
    source_title: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ErratumInfo:
    """
    One erratum record correcting the record being viewed.

    :param id: Erratum record id.
    :param title: Erratum title.
    """

    id: uuid.UUID
    title: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SiblingInfo:
    """
    One published or candidate row sharing a record's logical identity.

    :param id: Record id.
    :param kind: Published or candidate.
    :param source_id: Registration id.
    :param project: Project path.
    :param path: File path inside the project.
    :param ref: Branch/ref of the content.
    :param digest: Content digest.
    :param title: Display title.
    :param decision_date: Displayed decision date.
    :param decision_date_inferred: Whether the date is only inferred.
    :param approval_state: Approval state of this sibling's digest.
    """

    id: uuid.UUID
    kind: RecordState
    source_id: str
    project: str
    path: str
    ref: str
    digest: str
    title: str
    decision_date: datetime.date | None
    decision_date_inferred: bool
    approval_state: ApprovalStateCode


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordDetail:
    """
    Everything the record detail page shows.

    :param metadata: Identity and authored metadata.
    :param issues: Stored validation issues followed by read-time
        relationship issues (``missing_target``, ``ambiguous_target``,
        ``duplicate_uuid``).
    :param rendered_html: Sanitized HTML rendering of the body.
    :param provenance: Where the content came from.
    :param freshness: Freshness of the owning registration.
    :param outbound_links: Resolved outbound links, authored order.
    :param inbound_links: Inbound ``updated_by``/``obsoleted_by`` links.
    :param errata: Errata correcting this record.
    :param status: Derived display status.
    :param siblings: Every row (published and candidates) of this
        record's identity, including this one.
    :param legacy_signoff_unverified: Unverified legacy
        ``signed-off-by`` values; never an approval.
    :param approval: Approval state, policy summary and history.
    """

    metadata: RecordMetadata
    issues: tuple[Issue, ...]
    rendered_html: str
    provenance: RecordProvenance
    freshness: RecordFreshness
    outbound_links: tuple[OutboundLinkInfo, ...]
    inbound_links: tuple[InboundLinkInfo, ...]
    errata: tuple[ErratumInfo, ...]
    status: DisplayStatus
    siblings: tuple[SiblingInfo, ...]
    legacy_signoff_unverified: tuple[str, ...]
    approval: ApprovalSummary


def _summary(record: StoredRecord) -> RecordSummary:
    """
    Build the relationship summary of one stored row.

    :param record: The row.
    :returns: Its relationship summary, keyed by ``str(record.id)``.
    """
    return RecordSummary(
        key=str(record.id),
        identity=record.identity,
        adr_uuid=record.adr_uuid,
        links=record.links,
        record_kind=record.record_kind,
        path=record.path,
    )


def _relationship_index(
    store: CatalogStore, siblings: Sequence[StoredRecord]
) -> RelationshipIndex:
    """
    Build the relationship index for one detail request.

    Published rows form the index; *siblings* (every row of the
    detail record's identity, always including that record itself)
    are added for identities not already published. See the module
    docstring for why.

    :param store: Store of the caller's unit of work.
    :param siblings: Every row of the detail record's identity.
    :returns: The index.
    """
    summaries = {
        summary.key: summary
        for summary in store.list_relationship_summaries(RecordState.PUBLISHED)
    }
    for sibling in siblings:
        summaries.setdefault(str(sibling.id), _summary(sibling))
    return RelationshipIndex(summaries.values())


def _related_titles(
    store: CatalogStore, view: RelationshipView
) -> dict[str, str]:
    """
    Look up the title of every record referenced by a relationship view.

    One query per distinct related id (never per catalog row).

    :param store: Store of the caller's unit of work.
    :param view: The relationship view.
    :returns: Title by row key, for ids that still resolve to a row.
    """
    keys = {link.target_key for link in view.outbound if link.target_key}
    keys |= {link.source_key for link in view.inbound}
    keys |= set(view.errata)
    titles: dict[str, str] = {}
    for key in keys:
        related = store.get_record(uuid.UUID(key))
        if related is not None:
            titles[key] = related.title
    return titles


def _metadata(record: StoredRecord) -> RecordMetadata:
    """Build :class:`RecordMetadata` from a stored row."""
    return RecordMetadata(
        id=record.id,
        adr_uuid=record.adr_uuid,
        decision_date=record.decision_date,
        decision_date_inferred=record.decision_date_inferred,
        kind=record.kind,
        record_kind=record.record_kind,
        title=record.title,
        title_source=record.title_source,
        digest=record.digest,
        previous_digest=record.previous_digest,
    )


def _provenance(record: StoredRecord) -> RecordProvenance:
    """Build :class:`RecordProvenance` from a stored row."""
    return RecordProvenance(
        source_id=record.source_id,
        project=record.project,
        path=record.path,
        ref=record.ref,
        source_url=record.source_url,
    )


def _freshness(
    registration: Registration | None,
    now: datetime.datetime,
    stale_after_minutes: int,
) -> RecordFreshness:
    """Build :class:`RecordFreshness` for one record's registration."""
    return RecordFreshness(
        last_attempt_at=registration.last_attempt_at if registration else None,
        last_success_at=registration.last_success_at if registration else None,
        last_status=(
            registration.last_status if registration else PollStatus.NEVER
        ),
        stale=is_stale(registration, now, stale_after_minutes),
    )


def _outbound_links(
    links: Iterable[ResolvedLink], titles: dict[str, str]
) -> tuple[OutboundLinkInfo, ...]:
    """Convert resolved outbound links to :class:`OutboundLinkInfo`."""
    return tuple(
        OutboundLinkInfo(
            link_type=link.link_type,
            target_uuid=link.target_uuid,
            target_id=(uuid.UUID(link.target_key) if link.target_key else None),
            target_title=(
                titles.get(link.target_key) if link.target_key else None
            ),
            resolution=link.resolution,
            ambiguous=link.ambiguous,
            candidate_ids=tuple(uuid.UUID(key) for key in link.candidates),
        )
        for link in links
    )


def _inbound_links(
    links: Iterable[InboundLink], titles: dict[str, str]
) -> tuple[InboundLinkInfo, ...]:
    """Convert inbound links to :class:`InboundLinkInfo`."""
    return tuple(
        InboundLinkInfo(
            link_type=link.link_type,
            source_id=uuid.UUID(link.source_key),
            source_title=titles.get(link.source_key, ""),
        )
        for link in links
    )


def _errata(
    keys: Iterable[str], titles: dict[str, str]
) -> tuple[ErratumInfo, ...]:
    """Convert erratum row keys to :class:`ErratumInfo`."""
    return tuple(
        ErratumInfo(id=uuid.UUID(key), title=titles.get(key, ""))
        for key in keys
    )


def _siblings(
    siblings: Iterable[StoredRecord],
    policy: Policy | None,
    events: Sequence[DecisionEventView],
) -> tuple[SiblingInfo, ...]:
    """Build :class:`SiblingInfo` rows, each with its own approval state."""
    return tuple(
        SiblingInfo(
            id=sibling.id,
            kind=sibling.kind,
            source_id=sibling.source_id,
            project=sibling.project,
            path=sibling.path,
            ref=sibling.ref,
            digest=sibling.digest,
            title=sibling.title,
            decision_date=sibling.decision_date,
            decision_date_inferred=sibling.decision_date_inferred,
            approval_state=evaluate(
                policy, events, sibling.digest, is_approvable(sibling)
            ).state,
        )
        for sibling in siblings
    )


def _legacy_signoff(metadata: JsonObject) -> tuple[str, ...]:
    """
    Read the unverified legacy ``signed-off-by`` values, if any.

    Re-runs the same field validator used at ingest
    (:func:`app.domain.fields.parse_text_list`) over the stored raw
    frontmatter so the displayed values match what was validated,
    without duplicating that logic; the issues it could also return are
    not needed here (they are already in the record's stored issues).

    :param metadata: The record's stored frontmatter.
    :returns: The unverified sign-off entries.
    """
    raw = metadata.get("signed-off-by")
    if raw is None:
        return ()
    values, _issues = domain_fields.parse_text_list(raw, "signed-off-by")
    return values


def get_record_detail(
    store: CatalogStore,
    record_id: uuid.UUID,
    *,
    policy: Policy | None,
    policy_status: PolicyStatus,
    now: datetime.datetime,
    stale_after_minutes: int,
    reviewer: Reviewer | None = None,
) -> RecordDetail | None:
    """
    Assemble everything the record detail page shows.

    :param store: Store of the caller's unit of work.
    :param record_id: Record id.
    :param policy: The configured policy, or ``None`` if missing or
        invalid.
    :param policy_status: Configuration status of the policy.
    :param now: The current time (injected for testability).
    :param stale_after_minutes: Configured staleness threshold.
    :param reviewer: The caller, for ``approval.can_decide``; ``None``
        means nobody can decide.
    :returns: The detail, or ``None`` if the record does not exist.
    """
    record = store.get_record(record_id)
    if record is None:
        return None
    siblings = store.list_identity_siblings(record.identity)
    decision_events = store.list_decisions(record.identity)
    event_views = [event.as_view() for event in decision_events]
    index = _relationship_index(store, siblings)
    view = index.view(str(record.id))
    titles = _related_titles(store, view)
    registration = store.get_registration(record.source_id)
    return RecordDetail(
        metadata=_metadata(record),
        issues=tuple(record.issues) + view.issues,
        rendered_html=record.rendered_html,
        provenance=_provenance(record),
        freshness=_freshness(registration, now, stale_after_minutes),
        outbound_links=_outbound_links(view.outbound, titles),
        inbound_links=_inbound_links(view.inbound, titles),
        errata=_errata(view.errata, titles),
        status=view.status,
        siblings=_siblings(
            (s for s in siblings if s.id != record.id), policy, event_views
        ),
        legacy_signoff_unverified=_legacy_signoff(record.metadata),
        approval=build_approval(
            record=record,
            siblings=siblings,
            events=decision_events,
            policy=policy,
            policy_status=policy_status,
            reviewer=reviewer,
        ),
    )
