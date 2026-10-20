"""
Approval part of the record detail page (read-only).

Builds :class:`ApprovalSummary` for one record from its identity
siblings and decision events: the state of the current digest
(:func:`app.domain.approval.evaluate`), the full decision history of
the identity (each event marked ``current_digest``), divergence
between published and accepted/candidate content, competing
candidates, and whether **the caller** may decide now
(:func:`app.services.decisions.decision_blocker`, the same rules as the
decision endpoint).

Divergence (``divergence``, at most one):

- ``published_not_accepted`` -- the record is published, its current
  digest is not accepted, and another digest of the identity was
  accepted (typically an accepted candidate whose content differs from
  what was published). ``other_record_ids`` lists the rows currently
  holding that accepted digest (may be empty when no row holds it
  any more).
- ``published_differs`` -- the record is a candidate and the
  identity's published row holds different content.

Public API: :class:`PolicySummary`, :class:`DecisionProvenance`,
:class:`DecisionSummary`, :class:`DivergenceKind`,
:class:`DivergenceInfo`, :class:`CompetingCandidate`,
:class:`ApprovalSummary`, :func:`is_approvable`,
:func:`decision_summary`, :func:`build_approval`.
"""

import datetime
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.catalog_config import PolicyConfig
from app.domain.approval import (
    ApprovalStateCode,
    DecisionAction,
    DecisionEventView,
    Policy,
    PolicyStatus,
    evaluate,
)
from app.services.decisions import (
    Approvable,
    Reviewer,
    approval_blocker,
    decision_blocker,
)
from app.storage.port import DecisionEvent, RecordState, StoredRecord

__all__ = [
    "ApprovalSummary",
    "CompetingCandidate",
    "DecisionProvenance",
    "DecisionSummary",
    "DivergenceInfo",
    "DivergenceKind",
    "PolicySummary",
    "build_approval",
    "decision_summary",
    "is_approvable",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicySummary:
    """
    The applicable approval policy, or why there is none.

    :param status: Configured, missing or invalid.
    :param id: Policy id, when configured.
    :param version: Policy version, when configured.
    :param required: Whether approval is required, when configured.
    :param allow_self_approval: Whether authors may decide their own
        content, when configured.
    """

    status: PolicyStatus
    id: str | None
    version: int | None
    required: bool | None
    allow_self_approval: bool | None


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionProvenance:
    """
    The decided row as it was at decision time.

    :param record_id: Row id.
    :param kind: ``published`` or ``candidate``.
    :param source_id: Registration id.
    :param project: Project path.
    :param ref: Branch/ref.
    :param path: File path.
    :param source_url: Link to the content at the source.
    """

    record_id: str | None
    kind: str | None
    source_id: str | None
    project: str | None
    ref: str | None
    path: str | None
    source_url: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionSummary:
    """
    One append-only decision event of the identity.

    The reviewer's email is not exposed to readers.

    :param id: Stable event id.
    :param digest: Digest the decision applies to.
    :param current_digest: Whether *digest* is the viewed record's
        current digest.
    :param action: Accepted or rejected.
    :param actor_issuer: Reviewer token issuer.
    :param actor_subject: Reviewer token subject.
    :param actor_display: Reviewer display name, if known.
    :param comment: Optional reviewer comment.
    :param policy_id: Applied policy id.
    :param policy_version: Applied policy version.
    :param provenance: The decided row at decision time.
    :param created_at: Server timestamp of the decision.
    """

    id: uuid.UUID
    digest: str
    current_digest: bool
    action: DecisionAction
    actor_issuer: str
    actor_subject: str
    actor_display: str | None
    comment: str | None
    policy_id: str
    policy_version: int
    provenance: DecisionProvenance
    created_at: datetime.datetime


class DivergenceKind(StrEnum):
    """Kinds of published/accepted divergence (module docstring)."""

    PUBLISHED_NOT_ACCEPTED = "published_not_accepted"
    PUBLISHED_DIFFERS = "published_differs"


@dataclass(frozen=True, slots=True, kw_only=True)
class DivergenceInfo:
    """
    Content divergence within the identity.

    :param kind: Which divergence.
    :param other_digest: The accepted (or published) digest that
        differs from the current one.
    :param other_record_ids: Rows currently holding *other_digest*.
    :param other_accepted: Whether *other_digest* is accepted.
    :param message: Reader-facing explanation.
    """

    kind: DivergenceKind
    other_digest: str
    other_record_ids: tuple[uuid.UUID, ...]
    other_accepted: bool
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetingCandidate:
    """
    Another candidate of the identity with different content.

    :param id: Row id.
    :param ref: Branch/ref of the candidate.
    :param path: File path.
    :param digest: Its digest.
    :param approval_state: Approval state of its digest.
    """

    id: uuid.UUID
    ref: str
    path: str
    digest: str
    approval_state: ApprovalStateCode


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalSummary:
    """
    Approval state of a record's current content.

    :param state: The state code.
    :param needs_approval: Whether the record is in "Needs approval".
    :param digest: The current digest the state applies to.
    :param policy: The applicable policy summary.
    :param history: All decisions of this identity, oldest first.
    :param approvable: Whether the content can be decided at all.
    :param approval_blocker: Why not, when not approvable.
    :param last_accepted_digest: Latest accepted other digest, set for
        ``changed_since_acceptance``.
    :param can_decide: Whether **the caller** may decide now.
    :param decide_blocked_code: Stable code when the caller cannot.
    :param decide_blocked_reason: Reader-facing reason when not.
    :param divergence: Published/accepted divergence, if any.
    :param competing_candidates: Other candidates of the identity with
        different content.
    """

    state: ApprovalStateCode
    needs_approval: bool
    digest: str
    policy: PolicySummary
    history: tuple[DecisionSummary, ...]
    approvable: bool
    approval_blocker: str | None
    last_accepted_digest: str | None
    can_decide: bool
    decide_blocked_code: str | None
    decide_blocked_reason: str | None
    divergence: DivergenceInfo | None
    competing_candidates: tuple[CompetingCandidate, ...]


def is_approvable(record: Approvable) -> bool:
    """
    Tell whether a stored row's content may be decided at all.

    :param record: The row.
    :returns: ``True`` without identity or encoding errors.
    """
    return approval_blocker(record) is None


def _policy_summary(
    policy: Policy | None, status: PolicyStatus
) -> PolicySummary:
    """Build :class:`PolicySummary` from the configured policy."""
    return PolicySummary(
        status=status,
        id=policy.id if policy else None,
        version=policy.version if policy else None,
        required=policy.required if policy else None,
        allow_self_approval=policy.allow_self_approval if policy else None,
    )


def _text(value: object) -> str | None:
    """Return *value* if it is a string, else ``None``."""
    return value if isinstance(value, str) else None


def decision_summary(
    event: DecisionEvent, current_digest: str
) -> DecisionSummary:
    """
    Convert a stored event for the API.

    :param event: The stored event.
    :param current_digest: Digest of the viewed record.
    :returns: The summary.
    """
    raw = event.provenance
    return DecisionSummary(
        id=event.id,
        digest=event.digest,
        current_digest=event.digest == current_digest,
        action=event.action,
        actor_issuer=event.actor_issuer,
        actor_subject=event.actor_subject,
        actor_display=event.actor_display,
        comment=event.comment,
        policy_id=event.policy_id,
        policy_version=event.policy_version,
        provenance=DecisionProvenance(
            record_id=_text(raw.get("record_id")),
            kind=_text(raw.get("kind")),
            source_id=_text(raw.get("source_id")),
            project=_text(raw.get("project")),
            ref=_text(raw.get("ref")),
            path=_text(raw.get("path")),
            source_url=_text(raw.get("source_url")),
        ),
        created_at=event.created_at,
    )


def _latest_accepted(
    views: Iterable[DecisionEventView], exclude_digest: str
) -> DecisionEventView | None:
    """Latest acceptance of a digest other than *exclude_digest*."""
    accepted = [
        v
        for v in views
        if v.action is DecisionAction.ACCEPTED and v.digest != exclude_digest
    ]
    return max(accepted, key=lambda v: (v.created_at, v.id), default=None)


def _divergence(
    record: StoredRecord,
    siblings: Sequence[StoredRecord],
    views: Sequence[DecisionEventView],
    state: ApprovalStateCode,
) -> DivergenceInfo | None:
    """Detect divergence as described in the module docstring."""
    accepted_digests = {
        v.digest for v in views if v.action is DecisionAction.ACCEPTED
    }
    if record.kind is RecordState.PUBLISHED:
        if state is ApprovalStateCode.ACCEPTED:
            return None
        accepted = _latest_accepted(views, record.digest)
        if accepted is None:
            return None
        return DivergenceInfo(
            kind=DivergenceKind.PUBLISHED_NOT_ACCEPTED,
            other_digest=accepted.digest,
            other_record_ids=tuple(
                s.id for s in siblings if s.digest == accepted.digest
            ),
            other_accepted=True,
            message="a different revision of this ADR was accepted; the "
            "published content needs its own decision",
        )
    published = next(
        (s for s in siblings if s.kind is RecordState.PUBLISHED), None
    )
    if published is None or published.digest == record.digest:
        return None
    return DivergenceInfo(
        kind=DivergenceKind.PUBLISHED_DIFFERS,
        other_digest=published.digest,
        other_record_ids=(published.id,),
        other_accepted=published.digest in accepted_digests,
        message="the published revision of this ADR differs from this "
        "candidate",
    )


def _competing(
    record: StoredRecord,
    siblings: Iterable[StoredRecord],
    policy: Policy | None,
    views: Sequence[DecisionEventView],
) -> tuple[CompetingCandidate, ...]:
    """List the identity's other candidates with different content."""
    return tuple(
        CompetingCandidate(
            id=s.id,
            ref=s.ref,
            path=s.path,
            digest=s.digest,
            approval_state=evaluate(
                policy, views, s.digest, is_approvable(s)
            ).state,
        )
        for s in siblings
        if s.kind is RecordState.CANDIDATE
        and s.id != record.id
        and s.digest != record.digest
    )


def _caller_blocker(
    record: StoredRecord,
    events: Sequence[DecisionEvent],
    policy: Policy | None,
    policy_status: PolicyStatus,
    reviewer: Reviewer | None,
) -> tuple[str | None, str | None]:
    """
    Tell why the caller cannot decide now.

    :param record: The viewed record.
    :param events: Every decision event of its identity.
    :param policy: The configured policy, or ``None``.
    :param policy_status: Configuration status of the policy.
    :param reviewer: The caller, or ``None``.
    :returns: ``(code, reason)``, both ``None`` when the caller can.
    """
    if reviewer is None:
        return "anonymous", "sign in as a reviewer to decide"
    blocker = decision_blocker(
        record, events, PolicyConfig(policy_status, policy), reviewer
    )
    if blocker is None:
        return None, None
    return blocker.code, blocker.message


def build_approval(
    *,
    record: StoredRecord,
    siblings: Sequence[StoredRecord],
    events: Sequence[DecisionEvent],
    policy: Policy | None,
    policy_status: PolicyStatus,
    reviewer: Reviewer | None,
) -> ApprovalSummary:
    """
    Build the approval summary of one record for one caller.

    :param record: The viewed record.
    :param siblings: Every row of its identity (including itself).
    :param events: Every decision event of its identity.
    :param policy: The configured policy, or ``None``.
    :param policy_status: Configuration status of the policy.
    :param reviewer: The caller, or ``None`` (then nobody can decide).
    :returns: The summary.
    """
    views = [event.as_view() for event in events]
    blocker_reason = approval_blocker(record)
    state = evaluate(policy, views, record.digest, blocker_reason is None)
    code, reason = _caller_blocker(
        record, events, policy, policy_status, reviewer
    )
    return ApprovalSummary(
        state=state.state,
        needs_approval=state.needs_approval,
        digest=record.digest,
        policy=_policy_summary(policy, policy_status),
        history=tuple(decision_summary(e, record.digest) for e in events),
        approvable=blocker_reason is None,
        approval_blocker=blocker_reason,
        last_accepted_digest=(
            state.last_accepted.digest if state.last_accepted else None
        ),
        can_decide=code is None,
        decide_blocked_code=code,
        decide_blocked_reason=reason,
        divergence=_divergence(record, siblings, views, state.state),
        competing_candidates=_competing(record, siblings, policy, views),
    )
