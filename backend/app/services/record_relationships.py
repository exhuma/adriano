"""
Relationship part of the record detail page (read-only).

Builds a :class:`~app.domain.relationships.RelationshipIndex` for one
detail request and converts the record's view into API-ready values
(outbound/inbound links and errata with titles, display status and
read-time relationship issues).

Design decisions worth recording:

- **Links resolve by UUID.** A UUID identifies one ADR across every
  registration and project, so a link target is either in the catalog
  or missing; there are no resolution tiers and no ambiguity. Targets
  and inbound links are **published** ADRs; the viewed record takes
  part with the row actually shown (published or candidate), so a
  candidate's outbound links resolve against published ADRs.
  Candidates of *other* ADRs are not link targets.
- **Cost of the detail endpoint.** :meth:`~app.storage.port.
  CatalogStore.list_relationship_candidates` fetches only the
  published rows that can affect the viewed record (its own link
  targets and the rows linking back to it), not every published row
  (see ``docs/developer/performance.rst``). Titles of related records
  come from one more query (:meth:`~app.storage.port.CatalogStore.
  published_titles`).
- **Which errata belong to a record.** Errata are fetched by the
  record's UUID (:meth:`~app.storage.port.CatalogStore.
  list_errata_for`, published *and* candidate rows from every
  registration): every erratum whose ``erratum-for`` is the UUID
  belongs to the ADR, on its published row and on its candidates
  alike. An erratum row of the ADR itself (``erratum-for`` its own
  UUID) is not listed.
- **The erratum's own target.** On an erratum's page the ``corrects``
  link is reported as :class:`ErratumForInfo` and dropped from the
  outbound links.
- **Errata of errata.** An erratum never lists errata of its own (its
  page has no Errata section and a zero summary): errata correct
  decisions. An erratum whose ``erratum-for`` is another erratum keeps
  ``erratum_for.resolved`` but gets the read-time warning
  ``erratum_target_is_erratum``.

Public API: :class:`OutboundLinkInfo`, :class:`InboundLinkInfo`,
:class:`ErratumForInfo`, :class:`RecordRelationships`,
:func:`build_relationships`.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.issues import Issue, IssueCode, warning
from app.domain.relationships import (
    DisplayStatus,
    InboundLink,
    InboundType,
    RecordSummary,
    RelationshipIndex,
    RelationshipView,
    ResolvedLink,
)
from app.domain.values import LinkType, RecordKind
from app.storage.port import CatalogStore, ErratumRow, StoredRecord

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
    One outbound link and whether it resolved.

    :param link_type: The authored relationship.
    :param target_uuid: The authored target UUID; it addresses the
        target's published row (``/records/{uuid}``).
    :param resolved: Whether the target is in the catalog.
    :param target_title: Resolved target title, or ``None``.
    """

    link_type: LinkType
    target_uuid: uuid.UUID
    resolved: bool
    target_title: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class InboundLinkInfo:
    """
    A link from another record to the one being viewed.

    :param link_type: ``updated_by`` or ``obsoleted_by``.
    :param source_uuid: UUID of the linking record (a published ADR).
    :param source_title: Title of the linking record.
    """

    link_type: InboundType
    source_uuid: uuid.UUID
    source_title: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ErratumForInfo:
    """
    The decision an erratum corrects (its ``erratum-for``).

    :param uuid: The authored target UUID.
    :param title: Resolved target title, or ``None``.
    :param resolved: Whether the target is in the catalog.
    """

    uuid: uuid.UUID
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
        ``erratum_target_is_erratum``).
    """

    outbound_links: tuple[OutboundLinkInfo, ...]
    inbound_links: tuple[InboundLinkInfo, ...]
    errata: tuple[ErratumRow, ...]
    erratum_for: ErratumForInfo | None
    status: DisplayStatus
    issues: tuple[Issue, ...]


def _summaries(
    store: CatalogStore, record: StoredRecord
) -> dict[uuid.UUID, RecordSummary]:
    """
    Collect the summaries of the relationship index for one request.

    :param store: Store of the caller's unit of work.
    :param record: The row whose detail page is being assembled.
    :returns: Summaries by UUID: the related published ADRs plus the
        viewed row for its own UUID.
    """
    targets = [target for _link_type, target in record.links.pairs()]
    related = store.list_relationship_candidates(record.adr_uuid, targets)
    summaries = {summary.adr_uuid: summary for summary in related}
    summaries[record.adr_uuid] = RecordSummary(
        adr_uuid=record.adr_uuid,
        links=record.links,
        record_kind=record.record_kind,
    )
    return summaries


def _errata(
    store: CatalogStore, record: StoredRecord
) -> tuple[ErratumRow, ...]:
    """
    List the errata of the record (see the module docstring).

    :param store: Store of the caller's unit of work.
    :param record: The viewed record.
    :returns: The erratum rows, in store order.
    """
    if record.record_kind is RecordKind.ERRATUM:
        return ()
    rows = store.list_errata_for(record.adr_uuid)
    return tuple(row for row in rows if row.adr_uuid != record.adr_uuid)


def _erratum_target_issues(
    erratum_for: ErratumForInfo | None,
    summaries: dict[uuid.UUID, RecordSummary],
) -> tuple[Issue, ...]:
    """
    Flag an erratum whose ``erratum-for`` resolved to another erratum.

    The domain cannot see this at validation time (it needs the
    target's kind), so it is a read-time issue like ``missing_target``.

    :param erratum_for: The viewed erratum's target, if any.
    :param summaries: The record's relationship summaries.
    :returns: One warning, or nothing.
    """
    if erratum_for is None or not erratum_for.resolved:
        return ()
    target = summaries.get(erratum_for.uuid)
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
) -> dict[uuid.UUID, str]:
    """
    Look up the title of every record referenced by a relationship view.

    :param store: Store of the caller's unit of work.
    :param view: The relationship view.
    :returns: Title by UUID, for UUIDs with a published row.
    """
    uuids = {link.target_uuid for link in view.outbound if link.resolved}
    uuids |= {link.source_uuid for link in view.inbound}
    return store.published_titles(uuids)


def _outbound_links(
    links: Iterable[ResolvedLink], titles: dict[uuid.UUID, str]
) -> tuple[OutboundLinkInfo, ...]:
    """Convert resolved outbound links to :class:`OutboundLinkInfo`."""
    return tuple(
        OutboundLinkInfo(
            link_type=link.link_type,
            target_uuid=link.target_uuid,
            resolved=link.resolved,
            target_title=(
                titles.get(link.target_uuid) if link.resolved else None
            ),
        )
        for link in links
    )


def _inbound_links(
    links: Iterable[InboundLink], titles: dict[uuid.UUID, str]
) -> tuple[InboundLinkInfo, ...]:
    """Convert inbound links to :class:`InboundLinkInfo`."""
    return tuple(
        InboundLinkInfo(
            link_type=link.link_type,
            source_uuid=link.source_uuid,
            source_title=titles.get(link.source_uuid, ""),
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
                title=link.target_title,
                resolved=link.resolved,
            )
    return None


def build_relationships(
    store: CatalogStore, record: StoredRecord
) -> RecordRelationships:
    """
    Resolve the relationships of one record for its detail page.

    :param store: Store of the caller's unit of work.
    :param record: The viewed row (published or candidate).
    :returns: Links, errata, status and read-time issues.
    """
    summaries = _summaries(store, record)
    view = RelationshipIndex(summaries.values()).view(record.adr_uuid)
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
        errata=_errata(store, record),
        erratum_for=erratum_for,
        status=view.status,
        issues=view.issues + _erratum_target_issues(erratum_for, summaries),
    )
