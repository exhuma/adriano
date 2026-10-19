"""
Approval policy, approval-state evaluation and reviewer eligibility.

Approval evidence is scoped by the logical identity
``(source_id, project, record_key)`` and the content digest. The caller
passes only the decision events of one identity; :func:`evaluate` then
derives the state of the record's **current digest**. Rules, applied in
this order (storage queries that filter by state must mirror them):

1. no valid policy -> ``policy_missing`` (needs approval);
2. policy ``required: false`` -> ``not_required`` (no approval needed);
3. the latest event for the current digest is ``accepted`` ->
   ``accepted`` (no approval needed);
4. the latest event for the current digest is ``rejected`` ->
   ``rejected`` (needs approval);
5. an ``accepted`` event exists for another digest ->
   ``changed_since_acceptance`` (needs approval);
6. otherwise -> ``pending`` (needs approval).

``approvable`` (see :attr:`app.domain.records.ParsedRecord.approvable`)
does not change the state; it only controls
:attr:`ApprovalState.can_decide`. A record without a valid UUID or with
bad encoding therefore shows ``pending`` and cannot be decided.

Public API: :class:`PolicyStatus`, :class:`Policy`,
:class:`DecisionAction`, :class:`DecisionEventView`,
:class:`ApprovalStateCode`, :class:`ApprovalState`, :func:`evaluate`,
:func:`last_decided`, :func:`is_eligible`, :func:`principal`,
:func:`is_self_approval`.
"""

import datetime
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class PolicyStatus(StrEnum):
    """Configuration status of the global approval policy."""

    CONFIGURED = "configured"
    MISSING = "missing"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class Policy:
    """
    The single global approval policy (Phase 1).

    :param id: Policy identifier recorded with every decision.
    :param version: Policy version recorded with every decision.
    :param required: Whether approval is required at all.
    :param reviewer_users: Eligible principals as ``issuer|subject``.
    :param reviewer_roles: Eligible IdP role names.
    :param allow_self_approval: Whether authors may decide their own
        records.
    """

    id: str
    version: int
    required: bool = True
    reviewer_users: frozenset[str] = frozenset()
    reviewer_roles: frozenset[str] = frozenset()
    allow_self_approval: bool = False


class DecisionAction(StrEnum):
    """Formal decision recorded by a reviewer."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class DecisionEventView:
    """
    The fields of a decision event needed for state evaluation.

    :param id: Stable event id.
    :param digest: Content digest string the decision applies to.
    :param action: Accepted or rejected.
    :param created_at: Server timestamp of the decision.
    """

    id: str
    digest: str
    action: DecisionAction
    created_at: datetime.datetime


class ApprovalStateCode(StrEnum):
    """The six approval states of a record's current content."""

    POLICY_MISSING = "policy_missing"
    NOT_REQUIRED = "not_required"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CHANGED_SINCE_ACCEPTANCE = "changed_since_acceptance"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class ApprovalState:
    """
    Evaluated approval state of a record's current digest.

    :param state: The state code.
    :param needs_approval: Whether the record belongs in the "Needs
        approval" filter.
    :param current_event: Latest decision for the current digest, if any.
    :param last_accepted: Latest acceptance for another digest, set for
        ``changed_since_acceptance``.
    :param can_decide: Whether a reviewer may record a decision now.
    """

    state: ApprovalStateCode
    needs_approval: bool
    current_event: DecisionEventView | None = None
    last_accepted: DecisionEventView | None = None
    can_decide: bool = False


def _latest(
    events: Iterable[DecisionEventView],
) -> DecisionEventView | None:
    """
    Pick the most recent event.

    :param events: Candidate events.
    :returns: The event with the greatest ``created_at`` (ties broken by
        id for determinism), or ``None``.
    """
    return max(events, key=lambda e: (e.created_at, e.id), default=None)


def evaluate(
    policy: Policy | None,
    identity_events: Iterable[DecisionEventView],
    current_digest: str,
    approvable: bool,
) -> ApprovalState:
    """
    Evaluate the approval state of a record's current digest.

    :param policy: The configured policy, or ``None`` when it is missing
        or invalid.
    :param identity_events: All decision events of the record's logical
        identity (any digest).
    :param current_digest: Digest string of the record's current content.
    :param approvable: Whether the content may be decided at all.
    :returns: The state; see the module docstring for the rules.
    """
    if policy is None:
        return ApprovalState(ApprovalStateCode.POLICY_MISSING, True)
    if not policy.required:
        return ApprovalState(ApprovalStateCode.NOT_REQUIRED, False)
    events = list(identity_events)
    current = _latest(e for e in events if e.digest == current_digest)
    if current is not None:
        accepted = current.action is DecisionAction.ACCEPTED
        code = (
            ApprovalStateCode.ACCEPTED
            if accepted
            else ApprovalStateCode.REJECTED
        )
        return ApprovalState(code, not accepted, current_event=current)
    earlier = _latest(e for e in events if e.action is DecisionAction.ACCEPTED)
    if earlier is not None:
        return ApprovalState(
            ApprovalStateCode.CHANGED_SINCE_ACCEPTANCE,
            True,
            last_accepted=earlier,
            can_decide=approvable,
        )
    return ApprovalState(ApprovalStateCode.PENDING, True, can_decide=approvable)


def last_decided(
    identity_events: Iterable[DecisionEventView],
    *,
    exclude_digest: str | None = None,
) -> DecisionEventView | None:
    """
    Pick the default "from" revision for a diff.

    :param identity_events: All decision events of one identity.
    :param exclude_digest: Digest to ignore, typically the current one.
    :returns: The latest accepted event, else the latest rejected event,
        else ``None``.
    """
    events = [e for e in identity_events if e.digest != exclude_digest]
    accepted = _latest(e for e in events if e.action is DecisionAction.ACCEPTED)
    if accepted is not None:
        return accepted
    return _latest(e for e in events if e.action is DecisionAction.REJECTED)


def principal(issuer: str, subject: str) -> str:
    """
    Build the stable principal string used in reviewer allowlists.

    :param issuer: Token issuer.
    :param subject: Token subject.
    :returns: ``issuer|subject``.
    """
    return f"{issuer}|{subject}"


def is_eligible(
    policy: Policy | None,
    issuer: str,
    subject: str,
    roles: Iterable[str],
) -> bool:
    """
    Tell whether a caller may record decisions under the policy.

    Read permission never implies review: only the policy's reviewer
    users and roles are eligible.

    :param policy: The configured policy, or ``None`` if missing.
    :param issuer: Caller's token issuer.
    :param subject: Caller's token subject.
    :param roles: Caller's IdP roles.
    :returns: ``True`` if the caller is a listed user or holds a listed
        role; always ``False`` without a policy.
    """
    if policy is None:
        return False
    if principal(issuer, subject) in policy.reviewer_users:
        return True
    return not policy.reviewer_roles.isdisjoint(roles)


def is_self_approval(
    policy: Policy, reviewer_email: str | None, author: str | None
) -> bool:
    """
    Tell whether a decision would be a forbidden self-approval.

    :param policy: The configured policy.
    :param reviewer_email: The reviewer's verified email, if known.
    :param author: The record author (push request or commit author),
        if known.
    :returns: ``True`` when self-approval is disallowed and the
        verified email equals the author (case-insensitive).
    """
    if policy.allow_self_approval or not reviewer_email or not author:
        return False
    return reviewer_email.strip().casefold() == author.strip().casefold()
