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
- **Cost of the detail endpoint.** Building the published-row
  relationship index is one query over every published row, run again
  on every detail request; at the catalog sizes planned for Phase 1
  benchmarking (~20k records) this is not optimised further here
  (no caching, no incremental index). Flagged as a phase 09 performance
  item rather than solved prematurely, per the phase 05 task brief.
  Looking up the title of every related record is one query per related
  id (never per catalog row), so it stays bounded by the small number of
  links a record has, not by catalog size.

Public API: :class:`OutboundLinkInfo`, :class:`InboundLinkInfo`,
:class:`ErratumInfo`, :class:`RecordRelationships`,
:func:`build_relationships`.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.domain.issues import Issue
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
from app.domain.values import LinkType
from app.storage.port import CatalogStore, RecordState, StoredRecord

__all__ = [
    "ErratumInfo",
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
class ErratumInfo:
    """
    One erratum record correcting the record being viewed.

    :param id: Erratum record id.
    :param title: Erratum title.
    """

    id: uuid.UUID
    title: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordRelationships:
    """
    Relationship facts of one record, ready for the detail page.

    :param outbound_links: Resolved outbound links, authored order.
    :param inbound_links: Inbound ``updated_by``/``obsoleted_by`` links.
    :param errata: Errata correcting the record.
    :param status: Derived display status.
    :param issues: Read-time relationship issues (``missing_target``,
        ``ambiguous_target``, ``duplicate_uuid``).
    """

    outbound_links: tuple[OutboundLinkInfo, ...]
    inbound_links: tuple[InboundLinkInfo, ...]
    errata: tuple[ErratumInfo, ...]
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


def _relationship_index(
    store: CatalogStore, siblings: Sequence[StoredRecord]
) -> RelationshipIndex:
    """
    Build the relationship index for one detail request.

    Published rows form the index; *siblings* (every row of the
    detail record's identity, always including that record itself)
    are added for rows not already present. See the module docstring
    for why.

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
    view = _relationship_index(store, siblings).view(str(record.id))
    titles = _related_titles(store, view)
    return RecordRelationships(
        outbound_links=_outbound_links(view.outbound, titles),
        inbound_links=_inbound_links(view.inbound, titles),
        errata=_errata(view.errata, titles),
        status=view.status,
        issues=view.issues,
    )
