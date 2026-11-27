"""
Relationship resolution across a set of record summaries.

Outbound links are authored by UUID, and a UUID identifies exactly one
ADR across every registration and project. A link from record *S* to
UUID *U* therefore resolves when the set holds a summary for *U*; an
unknown UUID yields ``missing_target``. A record never resolves a link
to itself.

The caller passes one summary per ADR: normally its published row,
and, for the record being viewed, the row actually shown (which may be
one of its candidates).

From the resolved links the index derives, for one record:

- inbound links: ``updated_by`` / ``obsoleted_by``;
- errata: erratum records whose ``corrects`` link (authored as
  ``erratum-for``) targets the record;
- display status: ``obsoleted`` if anything obsoletes it, else
  ``updated`` if anything updates it, else ``active``.

Public API: :class:`DisplayStatus`, :class:`InboundType`,
:class:`RecordSummary`, :class:`ResolvedLink`, :class:`InboundLink`,
:class:`RelationshipView`, :class:`RelationshipIndex`,
:func:`resolve_relationships`.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.domain.issues import Issue, IssueCode, warning
from app.domain.values import Links, LinkType, RecordKind


class DisplayStatus(StrEnum):
    """Display status derived from inbound lifecycle links."""

    ACTIVE = "active"
    UPDATED = "updated"
    OBSOLETED = "obsoleted"


class InboundType(StrEnum):
    """Reverse names of the ``updates`` / ``obsoletes`` links."""

    UPDATED_BY = "updated_by"
    OBSOLETED_BY = "obsoleted_by"


_INBOUND = {
    LinkType.UPDATES: InboundType.UPDATED_BY,
    LinkType.OBSOLETES: InboundType.OBSOLETED_BY,
}


@dataclass(frozen=True, slots=True)
class RecordSummary:
    """
    The relationship-relevant facts about one ADR.

    :param adr_uuid: The ADR's UUID (its identity).
    :param links: Validated outbound links of the shown content.
    :param record_kind: Decision or erratum.
    """

    adr_uuid: uuid.UUID
    links: Links = Links()
    record_kind: RecordKind = RecordKind.DECISION


@dataclass(frozen=True, slots=True)
class ResolvedLink:
    """
    One outbound link and whether it resolved.

    :param link_type: The authored relationship.
    :param target_uuid: The authored target UUID.
    :param resolved: Whether the target is in the catalog.
    """

    link_type: LinkType
    target_uuid: uuid.UUID
    resolved: bool


@dataclass(frozen=True, slots=True)
class InboundLink:
    """
    A link from another record to this one.

    :param link_type: ``updated_by`` or ``obsoleted_by``.
    :param source_uuid: UUID of the linking record.
    """

    link_type: InboundType
    source_uuid: uuid.UUID


@dataclass(frozen=True, slots=True)
class RelationshipView:
    """
    All relationship facts for one record.

    :param adr_uuid: UUID of the record.
    :param outbound: Resolved outbound links in authored order.
    :param inbound: Inbound ``updated_by`` / ``obsoleted_by`` links.
    :param errata: UUIDs of errata correcting this record.
    :param status: Derived display status.
    :param issues: ``missing_target`` issues for this record.
    """

    adr_uuid: uuid.UUID
    outbound: tuple[ResolvedLink, ...]
    inbound: tuple[InboundLink, ...]
    errata: tuple[uuid.UUID, ...]
    status: DisplayStatus
    issues: tuple[Issue, ...]

    def inbound_uuids(self, link_type: InboundType) -> tuple[uuid.UUID, ...]:
        """
        List the UUIDs of inbound links of one type.

        :param link_type: The inbound type to select.
        :returns: Source UUIDs, e.g. the records obsoleting this one.
        """
        return tuple(
            link.source_uuid
            for link in self.inbound
            if link.link_type is link_type
        )

    def first_link(self, link_type: LinkType) -> ResolvedLink | None:
        """
        Find the first outbound link of one type (e.g. ``corrects``).

        :param link_type: The relationship to select.
        :returns: The link, or ``None`` if the record has none.
        """
        return next(
            (link for link in self.outbound if link.link_type is link_type),
            None,
        )


def _link_issue(link: ResolvedLink) -> Issue | None:
    """
    Describe an unresolved outbound link.

    :param link: The resolved link.
    :returns: A warning, or ``None`` if the link resolved.
    """
    if link.resolved:
        return None
    return warning(
        IssueCode.MISSING_TARGET,
        f"`{link.link_type.value}` target {link.target_uuid} was not "
        "found in the catalog",
    )


class RelationshipIndex:
    """
    Pre-computed relationships for a set of record summaries.

    Build it once per set of summaries, then call :meth:`view` per
    record. The index is not modified after construction.
    """

    def __init__(self, summaries: Iterable[RecordSummary]) -> None:
        """
        Index summaries and resolve every outbound link once.

        :param summaries: One summary per ADR UUID.
        :raises ValueError: If two summaries share a UUID.
        """
        self._records: dict[uuid.UUID, RecordSummary] = {}
        for summary in summaries:
            if summary.adr_uuid in self._records:
                raise ValueError(f"duplicate summary for {summary.adr_uuid}")
            self._records[summary.adr_uuid] = summary
        self._reverse: dict[uuid.UUID, list[tuple[LinkType, uuid.UUID]]] = (
            defaultdict(list)
        )
        for summary in self._records.values():
            for link in self._outbound(summary):
                if link.resolved:
                    self._reverse[link.target_uuid].append(
                        (link.link_type, summary.adr_uuid)
                    )

    def _outbound(self, summary: RecordSummary) -> tuple[ResolvedLink, ...]:
        """
        Resolve the outbound links of one record.

        :param summary: The linking record.
        :returns: Its links in authored order.
        """
        return tuple(
            ResolvedLink(
                link_type,
                target,
                target != summary.adr_uuid and target in self._records,
            )
            for link_type, target in summary.links.pairs()
        )

    def view(self, adr_uuid: uuid.UUID) -> RelationshipView:
        """
        Compute the relationship view of one record.

        :param adr_uuid: UUID of the record.
        :returns: Outbound, inbound, errata, status and issues.
        :raises KeyError: If *adr_uuid* is not in the index.
        """
        outbound = self._outbound(self._records[adr_uuid])
        reverse = self._reverse.get(adr_uuid, [])
        inbound = tuple(
            InboundLink(_INBOUND[link_type], source)
            for link_type, source in reverse
            if link_type in _INBOUND
        )
        errata = tuple(
            source
            for link_type, source in reverse
            if link_type is LinkType.CORRECTS
            and self._records[source].record_kind is RecordKind.ERRATUM
        )
        return RelationshipView(
            adr_uuid=adr_uuid,
            outbound=outbound,
            inbound=inbound,
            errata=errata,
            status=_status(inbound),
            issues=tuple(
                i for i in map(_link_issue, outbound) if i is not None
            ),
        )


def _status(inbound: tuple[InboundLink, ...]) -> DisplayStatus:
    """
    Derive the display status from inbound links.

    :param inbound: Inbound links of the record.
    :returns: ``obsoleted`` before ``updated`` before ``active``.
    """
    types = {link.link_type for link in inbound}
    if InboundType.OBSOLETED_BY in types:
        return DisplayStatus.OBSOLETED
    if InboundType.UPDATED_BY in types:
        return DisplayStatus.UPDATED
    return DisplayStatus.ACTIVE


def resolve_relationships(
    summaries: Iterable[RecordSummary], adr_uuid: uuid.UUID
) -> RelationshipView:
    """
    Compute the relationship view of one record in a single call.

    Use :class:`RelationshipIndex` directly when viewing many records.

    :param summaries: All summaries to resolve against.
    :param adr_uuid: UUID of the record of interest.
    :returns: The relationship view.
    :raises KeyError: If *adr_uuid* is not among *summaries*.
    """
    return RelationshipIndex(summaries).view(adr_uuid)
