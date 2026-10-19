"""Tests for approval-state evaluation (``app.domain.approval``)."""

import datetime

import pytest

from app.domain.approval import (
    ApprovalStateCode,
    DecisionAction,
    DecisionEventView,
    Policy,
    evaluate,
    is_eligible,
    is_self_approval,
    last_decided,
)

ISSUER = "https://idp.example.com"
POLICY = Policy(
    id="global",
    version=1,
    required=True,
    reviewer_users=frozenset({f"{ISSUER}|subject-123"}),
    reviewer_roles=frozenset({"adr-reviewer"}),
)
CURRENT = "sha256-v1:" + "a" * 64
OLDER = "sha256-v1:" + "b" * 64
T0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def event(
    digest: str, action: DecisionAction, minutes: int = 0, ident: str = ""
) -> DecisionEventView:
    """
    Build a decision event for tests.

    :param digest: Digest the decision applies to.
    :param action: Accepted or rejected.
    :param minutes: Offset from a fixed base time.
    :param ident: Event id (defaults to digest + offset).
    :returns: The event view.
    """
    return DecisionEventView(
        id=ident or f"{digest[-1]}{minutes}",
        digest=digest,
        action=action,
        created_at=T0 + datetime.timedelta(minutes=minutes),
    )


ACCEPT = DecisionAction.ACCEPTED
REJECT = DecisionAction.REJECTED


@pytest.mark.parametrize(
    ("policy", "events", "state", "needs"),
    [
        (None, [], ApprovalStateCode.POLICY_MISSING, True),
        (
            Policy(id="global", version=1, required=False),
            [],
            ApprovalStateCode.NOT_REQUIRED,
            False,
        ),
        (POLICY, [event(CURRENT, ACCEPT)], ApprovalStateCode.ACCEPTED, False),
        (POLICY, [event(CURRENT, REJECT)], ApprovalStateCode.REJECTED, True),
        (
            POLICY,
            [event(OLDER, ACCEPT)],
            ApprovalStateCode.CHANGED_SINCE_ACCEPTANCE,
            True,
        ),
        (POLICY, [], ApprovalStateCode.PENDING, True),
        (POLICY, [event(OLDER, REJECT)], ApprovalStateCode.PENDING, True),
    ],
    ids=[
        "policy-missing",
        "not-required",
        "accepted",
        "rejected",
        "changed-since-acceptance",
        "pending",
        "pending-after-older-rejection",
    ],
)
def test_approval_states(
    policy: Policy | None,
    events: list[DecisionEventView],
    state: ApprovalStateCode,
    needs: bool,
) -> None:
    """Ensure each approval state and its needs-approval flag."""
    result = evaluate(policy, events, CURRENT, approvable=True)

    assert (result.state, result.needs_approval) == (state, needs)


def test_rejected_for_current_hash_despite_earlier_acceptance() -> None:
    """Ensure a rejection of the current hash wins over older acceptance."""
    events = [event(OLDER, ACCEPT, 0), event(CURRENT, REJECT, 5)]

    result = evaluate(POLICY, events, CURRENT, approvable=True)

    assert result.state is ApprovalStateCode.REJECTED
    assert result.current_event == events[1]
    assert not result.can_decide


def test_changed_since_acceptance_reports_last_accepted() -> None:
    """Ensure the latest acceptance of another hash is reported."""
    events = [
        event(OLDER, ACCEPT, 0),
        event("sha256-v1:" + "c" * 64, ACCEPT, 9),
    ]

    result = evaluate(POLICY, events, CURRENT, approvable=True)

    assert result.last_accepted == events[1]
    assert result.can_decide


def test_missing_policy_is_not_treated_as_not_required() -> None:
    """Ensure a missing policy needs approval even with an acceptance."""
    result = evaluate(None, [event(CURRENT, ACCEPT)], CURRENT, True)

    assert result.state is ApprovalStateCode.POLICY_MISSING
    assert result.needs_approval
    assert not result.can_decide


def test_unapprovable_record_is_pending_and_cannot_be_decided() -> None:
    """Ensure records with identity errors show pending and no decide."""
    result = evaluate(POLICY, [], CURRENT, approvable=False)

    assert result.state is ApprovalStateCode.PENDING
    assert not result.can_decide


def test_pending_record_can_be_decided() -> None:
    """Ensure an approvable pending record may be decided."""
    result = evaluate(POLICY, [], CURRENT, approvable=True)

    assert result.can_decide


def test_last_decided_prefers_acceptance() -> None:
    """Ensure the diff base is the last acceptance before any rejection."""
    accepted = event(OLDER, ACCEPT, 0)
    rejected = event("sha256-v1:" + "c" * 64, REJECT, 10)

    assert last_decided([accepted, rejected]) == accepted


def test_last_decided_falls_back_to_rejection() -> None:
    """Ensure the diff base is the last rejection without acceptance."""
    first = event(OLDER, REJECT, 0)
    second = event("sha256-v1:" + "c" * 64, REJECT, 10)

    assert last_decided([first, second]) == second


def test_last_decided_excludes_current_digest() -> None:
    """Ensure the current digest can be excluded from the diff base."""
    events = [event(CURRENT, ACCEPT, 5), event(OLDER, REJECT, 0)]

    result = last_decided(events, exclude_digest=CURRENT)

    assert result == events[1]


def test_last_decided_without_events() -> None:
    """Ensure there is no diff base without decisions."""
    assert last_decided([]) is None


def test_eligible_by_user() -> None:
    """Ensure an allowlisted issuer|subject is eligible."""
    assert is_eligible(POLICY, ISSUER, "subject-123", [])


def test_user_from_other_issuer_not_eligible() -> None:
    """Ensure the same subject from another issuer is not eligible."""
    assert not is_eligible(POLICY, "https://evil.example", "subject-123", [])


def test_eligible_by_role() -> None:
    """Ensure a caller holding a reviewer role is eligible."""
    assert is_eligible(
        POLICY, ISSUER, "someone", ["adr-reader", "adr-reviewer"]
    )


def test_read_role_not_eligible() -> None:
    """Ensure read permission alone never implies review rights."""
    assert not is_eligible(POLICY, ISSUER, "someone", ["adr-reader", "admin"])


def test_no_policy_means_nobody_is_eligible() -> None:
    """Ensure nobody is eligible while the policy is missing."""
    assert not is_eligible(None, ISSUER, "subject-123", ["adr-reviewer"])


@pytest.mark.parametrize(
    ("allow", "email", "author", "expected"),
    [
        (False, "Alice@Example.com", "alice@example.com", True),
        (False, "bob@example.com", "alice@example.com", False),
        (False, "alice@example.com", None, False),
        (True, "alice@example.com", "alice@example.com", False),
    ],
)
def test_self_approval(
    allow: bool, email: str, author: str | None, expected: bool
) -> None:
    """Ensure self-approval is detected only when disallowed and known."""
    policy = Policy(id="global", version=1, allow_self_approval=allow)

    assert is_self_approval(policy, email, author) is expected
