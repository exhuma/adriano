"""
Relationship resolution across a set of record summaries.

Outbound links are authored by UUID. A link from record *S* to UUID *U*
resolves to the record with that UUID, preferring, in order:

1. the same project of the same registration (``same_project``),
2. the same registration (``same_registration``),
3. any registration (``global``).

Rows of one logical identity (the published row and its candidates on
other refs) are revisions of one decision, not separate targets: each
identity is represented by its published row, else by its most
recently updated candidate. If several identities (or several published
rows of one identity) share the best tier the link is *ambiguous*: it
is left unresolved and reported (``ambiguous_target``); nothing is
picked arbitrarily. An unknown UUID yields ``missing_target``. A record
never resolves a link to itself or to another revision of itself.

From the resolved links the index derives, for one record:

- inbound links: ``updated_by`` / ``obsoleted_by``;
- errata: erratum records whose ``corrects`` link (authored as
  ``erratum-for``) resolves to the record. The erratum's own outbound
  ``corrects`` link resolves like any other link;
- display status: ``obsoleted`` if anything obsoletes it, else
  ``updated`` if anything updates it, else ``active``;
- ``duplicate_uuid`` issues: an error when another *published* file of
  the same identity (same registration, project and UUID) uses the UUID
  (only for a published record), a warning when other identities use
  it. Candidates of the record's own identity are revisions and are
  never reported.

Records without a valid UUID take no part in UUID relationships.

Callers pass one summary per stored row: normally the published rows
plus, optionally, candidate rows (``published=False``).

Public API: :class:`DisplayStatus`, :class:`InboundType`,
:class:`Resolution`, :class:`RecordSummary`, :class:`ResolvedLink`,
:class:`InboundLink`, :class:`RelationshipView`,
:class:`RelationshipIndex`, :func:`resolve_relationships`.
"""

import datetime
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.domain.issues import Issue, IssueCode, error, warning
from app.domain.values import Identity, Links, LinkType, RecordKind


class DisplayStatus(StrEnum):
    """Display status derived from inbound lifecycle links."""

    ACTIVE = "active"
    UPDATED = "updated"
    OBSOLETED = "obsoleted"


class InboundType(StrEnum):
    """Reverse names of the ``updates`` / ``obsoletes`` links."""

    UPDATED_BY = "updated_by"
    OBSOLETED_BY = "obsoleted_by"


class Resolution(StrEnum):
    """Tier at which an outbound link was resolved."""

    SAME_PROJECT = "same_project"
    SAME_REGISTRATION = "same_registration"
    GLOBAL = "global"


_TIER_ORDER = (
    Resolution.SAME_PROJECT,
    Resolution.SAME_REGISTRATION,
    Resolution.GLOBAL,
)

_INBOUND = {
    LinkType.UPDATES: InboundType.UPDATED_BY,
    LinkType.OBSOLETES: InboundType.OBSOLETED_BY,
}


@dataclass(frozen=True, slots=True)
class RecordSummary:
    """
    The relationship-relevant facts about one stored record row.

    :param key: Caller-chosen unique row key (e.g. the record id).
    :param identity: Logical identity of the record.
    :param adr_uuid: Authored UUID, ``None`` if missing or invalid.
    :param links: Validated outbound links.
    :param record_kind: Decision or erratum.
    :param path: File path, used only in messages.
    :param published: ``True`` for a published row, ``False`` for a
        candidate (a revision on another ref).
    :param updated_at: When the row's content last changed; picks the
        representative candidate of an unpublished identity.
    """

    key: str
    identity: Identity
    adr_uuid: uuid.UUID | None
    links: Links = Links()
    record_kind: RecordKind = RecordKind.DECISION
    path: str = ""
    published: bool = True
    updated_at: datetime.datetime | None = None

    @property
    def label(self) -> str:
        """
        Human-readable location for messages.

        :returns: ``<source>/<project>/<path>`` or the row key.
        """
        if not self.path:
            return self.key
        ident = self.identity
        return f"{ident.source_id}/{ident.project}/{self.path}"


@dataclass(frozen=True, slots=True)
class ResolvedLink:
    """
    One outbound link and how it resolved.

    :param link_type: The authored relationship.
    :param target_uuid: The authored target UUID.
    :param target_key: Row key of the resolved target, or ``None``.
    :param resolution: Tier used, or ``None`` when unresolved.
    :param candidates: Row keys of equally good targets when ambiguous.
    """

    link_type: LinkType
    target_uuid: uuid.UUID
    target_key: str | None
    resolution: Resolution | None
    candidates: tuple[str, ...] = ()

    @property
    def ambiguous(self) -> bool:
        """
        Tell whether several targets matched at the best tier.

        :returns: ``True`` if the link is ambiguous.
        """
        return len(self.candidates) > 1


@dataclass(frozen=True, slots=True)
class InboundLink:
    """
    A link from another record to this one.

    :param link_type: ``updated_by`` or ``obsoleted_by``.
    :param source_key: Row key of the linking record.
    """

    link_type: InboundType
    source_key: str


@dataclass(frozen=True, slots=True)
class RelationshipView:
    """
    All relationship facts for one record.

    :param key: Row key of the record.
    :param outbound: Resolved outbound links in authored order.
    :param inbound: Inbound ``updated_by`` / ``obsoleted_by`` links.
    :param errata: Row keys of errata correcting this record.
    :param status: Derived display status.
    :param issues: ``missing_target``, ``ambiguous_target`` and
        ``duplicate_uuid`` issues for this record.
    """

    key: str
    outbound: tuple[ResolvedLink, ...]
    inbound: tuple[InboundLink, ...]
    errata: tuple[str, ...]
    status: DisplayStatus
    issues: tuple[Issue, ...]

    def inbound_keys(self, link_type: InboundType) -> tuple[str, ...]:
        """
        List the row keys of inbound links of one type.

        :param link_type: The inbound type to select.
        :returns: Source row keys, e.g. the records obsoleting this one.
        """
        return tuple(
            link.source_key
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


def _tier(source: Identity, target: Identity) -> Resolution:
    """
    Classify how close a target is to the linking record.

    :param source: Identity of the linking record.
    :param target: Identity of a candidate target.
    :returns: The resolution tier.
    """
    if source.source_id != target.source_id:
        return Resolution.GLOBAL
    if source.project != target.project:
        return Resolution.SAME_REGISTRATION
    return Resolution.SAME_PROJECT


_EPOCH = datetime.datetime.min.replace(tzinfo=datetime.UTC)


def _recency(summary: RecordSummary) -> tuple[datetime.datetime, str]:
    """
    Order candidates by recency, ties broken by key for determinism.

    :param summary: A candidate row.
    :returns: A sort key; larger is more recent.
    """
    return (summary.updated_at or _EPOCH, summary.key)


def _representatives(
    rows: Iterable[RecordSummary],
) -> list[RecordSummary]:
    """
    Collapse rows to one representative per logical identity.

    An identity is represented by its published rows (several only for
    a genuine duplicate), else by its most recently updated candidate.

    :param rows: Rows sharing one UUID.
    :returns: Representatives, sorted by key.
    """
    groups: dict[Identity, list[RecordSummary]] = defaultdict(list)
    for row in rows:
        groups[row.identity].append(row)
    chosen: list[RecordSummary] = []
    for group in groups.values():
        published = [row for row in group if row.published]
        chosen += published or [max(group, key=_recency)]
    return sorted(chosen, key=lambda row: row.key)


def _labels(rows: Sequence[RecordSummary]) -> str:
    """
    Join row labels for a message.

    :param rows: The rows.
    :returns: Sorted, comma-separated labels.
    """
    return ", ".join(sorted(row.label for row in rows))


def _link_issue(link: ResolvedLink) -> Issue | None:
    """
    Describe an unresolved outbound link.

    :param link: The resolved link.
    :returns: A warning, or ``None`` if the link resolved.
    """
    name = f"`{link.link_type.value}` target {link.target_uuid}"
    if link.ambiguous:
        count = len(link.candidates)
        return warning(
            IssueCode.AMBIGUOUS_TARGET,
            f"{name} matches {count} records equally; make the UUIDs unique",
        )
    if link.target_key is None:
        return warning(
            IssueCode.MISSING_TARGET,
            f"{name} was not found in the catalog",
        )
    return None


class RelationshipIndex:
    """
    Pre-computed relationships for a set of record summaries.

    Build it once per set of summaries, then call :meth:`view` per
    record. The index is not modified after construction.
    """

    def __init__(self, summaries: Iterable[RecordSummary]) -> None:
        """
        Index summaries and resolve every outbound link once.

        :param summaries: One summary per row; keys must be unique.
        :raises ValueError: If two summaries share a key.
        """
        self._records: dict[str, RecordSummary] = {}
        self._by_uuid: dict[uuid.UUID, list[RecordSummary]] = defaultdict(list)
        for summary in summaries:
            if summary.key in self._records:
                raise ValueError(f"duplicate summary key {summary.key!r}")
            self._records[summary.key] = summary
            if summary.adr_uuid is not None:
                self._by_uuid[summary.adr_uuid].append(summary)
        self._outbound: dict[str, tuple[ResolvedLink, ...]] = {}
        self._reverse: dict[str, list[tuple[LinkType, str]]] = defaultdict(list)
        for summary in self._records.values():
            self._index_outbound(summary)

    def _index_outbound(self, summary: RecordSummary) -> None:
        """
        Resolve the outbound links of one record and record reverses.

        :param summary: The linking record.
        """
        if summary.adr_uuid is None:
            self._outbound[summary.key] = ()
            return
        resolved = tuple(
            self._resolve(summary, link_type, target)
            for link_type, target in summary.links.pairs()
        )
        self._outbound[summary.key] = resolved
        for link in resolved:
            if link.target_key is not None:
                self._reverse[link.target_key].append(
                    (link.link_type, summary.key)
                )

    def _resolve(
        self, source: RecordSummary, link_type: LinkType, target: uuid.UUID
    ) -> ResolvedLink:
        """
        Resolve one outbound link by UUID with tier preference.

        :param source: The linking record.
        :param link_type: The relationship.
        :param target: The target UUID.
        :returns: The resolved (or unresolved) link.
        """
        candidates = [
            other
            for other in self._by_uuid.get(target, [])
            if other.identity != source.identity
        ]
        for tier in _TIER_ORDER:
            best = [
                other.key
                for other in _representatives(
                    other
                    for other in candidates
                    if _tier(source.identity, other.identity) is tier
                )
            ]
            if len(best) == 1:
                return ResolvedLink(link_type, target, best[0], tier)
            if best:
                return ResolvedLink(link_type, target, None, None, tuple(best))
        return ResolvedLink(link_type, target, None, None)

    def _duplicate_issues(self, summary: RecordSummary) -> list[Issue]:
        """
        Report other identities and published files using the UUID.

        Candidates of the record's own identity are revisions of it, not
        duplicates. Another published row of the same identity is a
        genuine duplicate (two files claiming one UUID), reported on
        published rows only.

        :param summary: The record to check.
        :returns: At most one error (same identity) and one warning
            (other identities).
        """
        if summary.adr_uuid is None:
            return []
        others = [
            other
            for other in self._by_uuid[summary.adr_uuid]
            if other.key != summary.key
        ]
        same = [
            other
            for other in others
            if other.identity == summary.identity
            and other.published
            and summary.published
        ]
        elsewhere = _representatives(
            other for other in others if other.identity != summary.identity
        )
        issues: list[Issue] = []
        if same:
            issues.append(
                error(
                    IssueCode.DUPLICATE_UUID,
                    f"UUID {summary.adr_uuid} is also used in the same "
                    f"project by {_labels(same)}; give each file its "
                    f"own UUID",
                )
            )
        if elsewhere:
            issues.append(
                warning(
                    IssueCode.DUPLICATE_UUID,
                    f"UUID {summary.adr_uuid} is also used by "
                    f"{_labels(elsewhere)}; these are separate records",
                )
            )
        return issues

    def view(self, key: str) -> RelationshipView:
        """
        Compute the relationship view of one record.

        :param key: Row key of the record.
        :returns: Outbound, inbound, errata, status and issues.
        :raises KeyError: If *key* is not in the index.
        """
        summary = self._records[key]
        outbound = self._outbound[key]
        reverse = self._reverse.get(key, [])
        inbound = tuple(
            InboundLink(_INBOUND[link_type], source_key)
            for link_type, source_key in reverse
            if link_type in _INBOUND
        )
        errata = tuple(
            source_key
            for link_type, source_key in reverse
            if link_type is LinkType.CORRECTS
            and self._records[source_key].record_kind is RecordKind.ERRATUM
        )
        issues = [i for i in map(_link_issue, outbound) if i is not None]
        issues += self._duplicate_issues(summary)
        return RelationshipView(
            key=key,
            outbound=outbound,
            inbound=inbound,
            errata=errata,
            status=_status(inbound),
            issues=tuple(issues),
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
    summaries: Iterable[RecordSummary], key: str
) -> RelationshipView:
    """
    Compute the relationship view of one record in a single call.

    Use :class:`RelationshipIndex` directly when viewing many records.

    :param summaries: All summaries to resolve against.
    :param key: Row key of the record of interest.
    :returns: The relationship view.
    :raises KeyError: If *key* is not among *summaries*.
    """
    return RelationshipIndex(summaries).view(key)
