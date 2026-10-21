"""
Relationship part of the record detail page (read-only).

Builds a :class:`~app.domain.relationships.RelationshipIndex` for one
detail request and converts the record's view into API-ready values
(outbound/inbound links and errata with titles, display status and
read-time relationship issues).

Design decisions worth recording for later phases:

- **Candidate participation in relationships.** The index is built from
  the published rows (:meth:`~app.storage.port.CatalogStore.
  list_relationship_summaries`) plus the identity siblings of the record
  whose detail is requested (:meth:`~app.storage.port.CatalogStore.
  list_identity_siblings`, which always includes the queried record
  itself, published or candidate). Siblings are marked published or
  candidate, so the domain treats rows of one identity as revisions
  (never as ``duplicate_uuid``, never as an ambiguous link target). A
  candidate's outbound links therefore resolve against published rows
  and its own identity's other rows only; links authored by *other*
  candidates (of a different identity) are never resolved against
  anything. This also means ``duplicate_uuid`` detection for a
  candidate's detail view does not see duplicates held only by
  unrelated candidates. Revisit if a later phase needs candidates to
  participate more broadly.
- **Cost of the detail endpoint.** Phase 09 benchmarking at 20,000
  published records measured the naive "fetch every published row"
  index build at ~780 ms per detail request, of which ~630 ms was
  spent fetching and converting all 20,000 rows to
  :class:`~app.domain.relationships.RecordSummary` in Python -- the
  Postgres scan itself took ~80 ms (see
  ``docs/developer/performance.rst``). Since this one request only ever
  looks at *one* record's view of the index, :meth:`~app.storage.port.
  CatalogStore.list_relationship_candidates` fetches only the published
  rows that can possibly affect that view (sharing the record's UUID,
  matching one of its own link targets, or linking back to it) instead
  of every published row; see its docstring for why the result is
  exactly the summary set the full fetch would have narrowed the index
  to for this one record. Looking up the title of every related record
  is one query per related id (never per catalog row), so it stays
  bounded by the small number of links a record has, not by catalog
  size.

- **Which errata belong to a record.** Errata are fetched by the
  record's UUID (:meth:`~app.storage.port.CatalogStore.
  list_errata_for`, published *and* candidate rows from every
  registration) and added to the index with only their ``corrects``
  link. An erratum belongs to the record when that link resolves --
  with the usual same-project, same-registration, global tiers -- to
  a row of the record's own identity (the published row, or the
  newest candidate when nothing is published). So an erratum in
  another project is not shown when a decision with the same UUID
  exists closer to it, an ambiguous ``erratum-for`` belongs to no
  record, and the errata of a decision show on its published row and
  on its candidate revisions alike. As for other links, candidates of
  *other* identities are not link targets.
- **The erratum's own target.** On an erratum's page the ``corrects``
  link is reported as :class:`ErratumForInfo` and dropped from the
  outbound links.
- **Errata of errata.** An erratum never lists errata of its own (its
  page has no Errata section and a zero summary): errata correct
  decisions. An erratum whose ``erratum-for`` resolves to another
  erratum keeps ``erratum_for.resolved`` but gets the read-time
  warning ``erratum_target_is_erratum``.

Public API: :class:`OutboundLinkInfo`, :class:`InboundLinkInfo`,
:class:`ErratumForInfo`, :class:`RecordRelationships`,
:func:`build_relationships`.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.domain.issues import Issue, IssueCode, warning
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
from app.domain.values import Links, LinkType, RecordKind
from app.storage.port import (
    CatalogStore,
    ErratumRow,
    RecordState,
    StoredRecord,
)

__all__ = [
    "ErratumForInfo",
    "InboundLinkInfo",
    "OutboundLinkInfo",
    "RecordRelationships",
    "build_relationships",
]


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
class ErratumForInfo:
    """
    The decision an erratum corrects (its ``erratum-for``).

    :param uuid: The authored target UUID.
    :param id: Resolved target record id, or ``None``.
    :param title: Resolved target title, or ``None``.
    :param resolved: Whether the link resolved to exactly one record.
    """

    uuid: uuid.UUID
    id: uuid.UUID | None
    title: str | None
    resolved: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordRelationships:
    """
    Relationship facts of one record, ready for the detail page.

    :param outbound_links: Resolved outbound links, authored order;
        without an erratum's own ``corrects`` link.
    :param inbound_links: Inbound ``updated_by``/``obsoleted_by`` links.
    :param errata: Erratum rows (published first, then candidates)
        that belong to the record; see the module docstring.
    :param erratum_for: For an erratum, the decision it corrects.
    :param status: Derived display status.
    :param issues: Read-time relationship issues (``missing_target``,
        ``ambiguous_target``, ``duplicate_uuid``,
        ``erratum_target_is_erratum``).
    """

    outbound_links: tuple[OutboundLinkInfo, ...]
    inbound_links: tuple[InboundLinkInfo, ...]
    errata: tuple[ErratumRow, ...]
    erratum_for: ErratumForInfo | None
    status: DisplayStatus
    issues: tuple[Issue, ...]


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
        published=record.kind is RecordState.PUBLISHED,
        updated_at=record.updated_at,
    )


def _relationship_summaries(
    store: CatalogStore,
    record: StoredRecord,
    siblings: Sequence[StoredRecord],
) -> dict[str, RecordSummary]:
    """
    Collect the summaries of the relationship index for one request.

    Only the published rows that can affect *record*'s own view are
    fetched (:meth:`~app.storage.port.CatalogStore.
    list_relationship_candidates`; see the module docstring "Cost of
    the detail endpoint"); *siblings* (every row of the detail
    record's identity, always including that record itself) are added
    for rows not already present. A record without a valid UUID has
    no possible relationships (nothing can target a UUID it does not
    have), so no candidate query is needed for it.

    :param store: Store of the caller's unit of work.
    :param record: The record whose detail page is being assembled.
    :param siblings: Every row of the detail record's identity.
    :returns: Summaries by row key.
    """
    if record.adr_uuid is None:
        summaries: dict[str, RecordSummary] = {}
    else:
        targets = [target for _link_type, target in record.links.pairs()]
        candidates = store.list_relationship_candidates(
            record.adr_uuid, targets
        )
        summaries = {summary.key: summary for summary in candidates}
    for sibling in siblings:
        summaries.setdefault(str(sibling.id), _summary(sibling))
    return summaries


def _erratum_summary(row: ErratumRow, target: uuid.UUID) -> RecordSummary:
    """
    Build the summary of an erratum row with only its ``corrects`` link.

    :param row: The erratum row.
    :param target: The UUID it corrects.
    :returns: Its summary, keyed by ``str(row.id)``.
    """
    return RecordSummary(
        key=str(row.id),
        identity=row.identity,
        adr_uuid=row.adr_uuid,
        links=Links(corrects=target),
        record_kind=RecordKind.ERRATUM,
        path=row.path,
        published=row.kind is RecordState.PUBLISHED,
        updated_at=row.updated_at,
    )


def _resolved_errata(
    store: CatalogStore,
    record: StoredRecord,
    siblings: Sequence[StoredRecord],
    summaries: dict[str, RecordSummary],
) -> tuple[ErratumRow, ...]:
    """
    Select the errata whose ``corrects`` link resolves to the record.

    See the module docstring "Which errata belong to a record".

    :param store: Store of the caller's unit of work.
    :param record: The viewed record.
    :param siblings: Every row of its identity.
    :param summaries: The record's relationship summaries.
    :returns: The matching erratum rows, in store order.
    """
    if record.adr_uuid is None or record.record_kind is RecordKind.ERRATUM:
        return ()
    rows = store.list_errata_for(record.adr_uuid)
    if not rows:
        return ()
    extended = dict(summaries)
    for row in rows:
        extended.setdefault(str(row.id), _erratum_summary(row, record.adr_uuid))
    index = RelationshipIndex(extended.values())
    own = {str(sibling.id) for sibling in siblings} | {str(record.id)}
    return tuple(row for row in rows if _corrects_key(index, row) in own)


def _corrects_key(index: RelationshipIndex, row: ErratumRow) -> str | None:
    """
    Find the row key an erratum's ``corrects`` link resolved to.

    :param index: Index containing the erratum row.
    :param row: The erratum row.
    :returns: The resolved key, or ``None``.
    """
    link = index.view(str(row.id)).first_link(LinkType.CORRECTS)
    return None if link is None else link.target_key


def _erratum_target_issues(
    erratum_for: ErratumForInfo | None,
    summaries: dict[str, RecordSummary],
) -> tuple[Issue, ...]:
    """
    Flag an erratum whose ``erratum-for`` resolved to another erratum.

    The domain cannot see this at validation time (it needs the
    target's kind), so it is a read-time issue like ``missing_target``.

    :param erratum_for: The viewed erratum's target, if any.
    :param summaries: The record's relationship summaries.
    :returns: One warning, or nothing.
    """
    if erratum_for is None or erratum_for.id is None:
        return ()
    target = summaries.get(str(erratum_for.id))
    if target is None or target.record_kind is not RecordKind.ERRATUM:
        return ()
    return (
        warning(
            IssueCode.ERRATUM_TARGET_IS_ERRATUM,
            f"`erratum-for` {erratum_for.uuid} is another erratum; an "
            "erratum should correct a decision, so point it at the "
            "decision the corrected erratum is for",
        ),
    )


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
    titles: dict[str, str] = {}
    for key in keys:
        related = store.get_record(uuid.UUID(key))
        if related is not None:
            titles[key] = related.title
    return titles


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


def _erratum_for(
    record: StoredRecord, links: Iterable[OutboundLinkInfo]
) -> ErratumForInfo | None:
    """
    Report the decision an erratum corrects.

    :param record: The viewed record.
    :param links: Its resolved outbound links.
    :returns: The target, or ``None`` for a decision or an erratum
        without a valid ``erratum-for``.
    """
    if record.record_kind is not RecordKind.ERRATUM:
        return None
    for link in links:
        if link.link_type is LinkType.CORRECTS:
            return ErratumForInfo(
                uuid=link.target_uuid,
                id=link.target_id,
                title=link.target_title,
                resolved=link.target_id is not None,
            )
    return None


def build_relationships(
    store: CatalogStore,
    record: StoredRecord,
    siblings: Sequence[StoredRecord],
) -> RecordRelationships:
    """
    Resolve the relationships of one record for its detail page.

    :param store: Store of the caller's unit of work.
    :param record: The viewed record.
    :param siblings: Every row of its identity (including itself).
    :returns: Links, errata, status and read-time issues.
    """
    summaries = _relationship_summaries(store, record, siblings)
    view = RelationshipIndex(summaries.values()).view(str(record.id))
    titles = _related_titles(store, view)
    outbound = _outbound_links(view.outbound, titles)
    erratum_for = _erratum_for(record, outbound)
    if erratum_for is not None:
        outbound = tuple(
            link for link in outbound if link.link_type is not LinkType.CORRECTS
        )
    return RecordRelationships(
        outbound_links=outbound,
        inbound_links=_inbound_links(view.inbound, titles),
        errata=_resolved_errata(store, record, siblings, summaries),
        erratum_for=erratum_for,
        status=view.status,
        issues=view.issues + _erratum_target_issues(erratum_for, summaries),
    )
