"""
Read-only record detail assembly.

:func:`get_record_detail` takes a :class:`~app.storage.port.
CatalogStore` (already inside a unit of work opened by the caller) plus
plain values, and returns a plain :class:`RecordDetail`; nothing here
imports FastAPI or a source adapter. Routers convert it with
``RecordDetailOut.model_validate(value)``.

The relationship part comes from
:mod:`app.services.record_relationships`, the approval part from
:mod:`app.services.approval_view`; this module adds metadata,
provenance, freshness, identity siblings and legacy sign-offs.

Public API: :class:`RecordMetadata`, :class:`RecordProvenance`,
:class:`RecordFreshness`, :class:`SiblingInfo`, :class:`RecordDetail`,
:func:`get_record_detail`.
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
from app.domain.issues import Issue
from app.domain.relationships import DisplayStatus
from app.domain.values import RecordKind, TitleSource
from app.services.approval_view import (
    ApprovalSummary,
    build_approval,
    is_approvable,
)
from app.services.decisions import Reviewer
from app.services.record_relationships import (
    ErratumInfo,
    InboundLinkInfo,
    OutboundLinkInfo,
    build_relationships,
)
from app.services.sources_view import is_stale
from app.storage.port import (
    CatalogStore,
    JsonObject,
    PollStatus,
    RecordState,
    Registration,
    StoredRecord,
)

__all__ = [
    "RecordDetail",
    "RecordFreshness",
    "RecordMetadata",
    "RecordProvenance",
    "SiblingInfo",
    "get_record_detail",
]


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
    relationships = build_relationships(store, record, siblings)
    registration = store.get_registration(record.source_id)
    return RecordDetail(
        metadata=_metadata(record),
        issues=tuple(record.issues) + relationships.issues,
        rendered_html=record.rendered_html,
        provenance=_provenance(record),
        freshness=_freshness(registration, now, stale_after_minutes),
        outbound_links=relationships.outbound_links,
        inbound_links=relationships.inbound_links,
        errata=relationships.errata,
        status=relationships.status,
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
