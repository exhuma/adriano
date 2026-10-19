"""
Formal accept/reject decisions (``POST /api/v1/records/{id}/decisions``).

A decision binds to the record's logical identity and the digest of its
**current** content at request time; the server sets the event id and
timestamp. Checks, in this order (the same rules give the detail
page's ``can_decide`` through :func:`decision_blocker`):

1. the record exists -> else 404 ``record_not_found``;
2. the approval policy is configured -> else 409 ``policy_missing``;
3. the policy requires approval -> else 409 ``approval_not_required``;
4. the caller is a policy reviewer (``issuer|subject`` or a role) ->
   else 403 ``not_eligible``;
5. the content is approvable (valid UUID, valid UTF-8) -> else 409
   ``not_approvable``;
6. not a self-approval (when the policy disallows it) -> else 403
   ``self_approval``. Self-approval means the reviewer's verified
   email equals the record ``author`` (case-insensitive), or the author
   equals the reviewer's ``issuer|subject`` exactly. Records without an
   author (polled filesystem/GitLab rows) cannot be detected;
7. ``expected_digest``, when sent, equals the current digest -> else
   409 ``digest_changed`` (the reviewer never decides content they did
   not see);
8. no decision exists for (identity, digest) -> else 409
   ``already_decided`` (also on a concurrent race, through the unique
   constraint).

Events are append-only (database trigger); nothing here updates or
deletes one.

Public API: :class:`Reviewer`, :class:`DecisionBlocker`,
:func:`approval_blocker`, :func:`decision_blocker`,
:func:`record_decision`.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.auth.rbac import reviewer_eligibility
from app.catalog_config import PolicyConfig
from app.domain.approval import (
    DecisionAction,
    Policy,
    is_self_approval,
    principal,
)
from app.domain.issues import IssueCode
from app.errors import (
    AdrianoError,
    ConflictError,
    DecisionExistsError,
    ForbiddenError,
    NotFoundError,
)
from app.storage.port import (
    CatalogStoreProvider,
    DecisionEvent,
    NewDecision,
    StoredRecord,
)

__all__ = [
    "DecisionBlocker",
    "Reviewer",
    "approval_blocker",
    "decision_blocker",
    "record_decision",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class Reviewer:
    """
    The caller of a decision, from verified token claims.

    :param issuer: Token issuer.
    :param subject: Token subject.
    :param display: Display name.
    :param email: Verified email, if known.
    :param roles: IdP roles.
    """

    issuer: str
    subject: str
    display: str | None
    email: str | None
    roles: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionBlocker:
    """
    Why the caller cannot decide a record now.

    :param code: Stable machine-readable code.
    :param message: Reader-facing reason.
    :param hint: What can be done about it.
    :param forbidden: ``True`` for caller-specific refusals (HTTP 403),
        ``False`` for state conflicts (HTTP 409).
    """

    code: str
    message: str
    hint: str
    forbidden: bool = False

    def to_error(self) -> AdrianoError:
        """
        Convert to the domain error raised by the decision endpoint.

        :returns: A :class:`ForbiddenError` or :class:`ConflictError`.
        """
        error_type = ForbiddenError if self.forbidden else ConflictError
        return error_type(self.message, code=self.code, hint=self.hint)


def approval_blocker(record: StoredRecord) -> str | None:
    """
    Explain why a stored row's content cannot be decided at all.

    Mirrors :attr:`app.domain.records.ParsedRecord.approval_blocker`.

    :param record: The row.
    :returns: A reader-facing reason, or ``None`` if approvable.
    """
    if any(i.code is IssueCode.BAD_ENCODING for i in record.issues):
        return "the file is not valid UTF-8"
    if record.adr_uuid is None:
        return "the record has no valid `uuid`"
    return None


def _is_self(policy: Policy, reviewer: Reviewer, author: str | None) -> bool:
    """
    Tell whether the reviewer is the record author (when disallowed).

    :param policy: The configured policy.
    :param reviewer: The caller.
    :param author: The record author, if known.
    :returns: ``True`` for a forbidden self-approval.
    """
    if is_self_approval(policy, reviewer.email, author):
        return True
    if policy.allow_self_approval or not author:
        return False
    return author.strip() == principal(reviewer.issuer, reviewer.subject)


def _policy_blocker(
    policy_config: PolicyConfig | None, reviewer: Reviewer
) -> DecisionBlocker | None:
    """Apply checks 2-4 of the module docstring."""
    policy = policy_config.policy if policy_config is not None else None
    if policy_config is None or policy is None:
        return DecisionBlocker(
            code="policy_missing",
            message="the approval policy is not configured or invalid; "
            "decisions are refused",
            hint="an operator must fix `approval_policy` in catalog.yaml "
            "(see `adriano check-config`) and restart",
        )
    if not policy.required:
        return DecisionBlocker(
            code="approval_not_required",
            message="the approval policy does not require approval",
            hint="no decision is needed",
        )
    eligibility = reviewer_eligibility(
        policy_config,
        issuer=reviewer.issuer,
        subject=reviewer.subject,
        roles=reviewer.roles,
    )
    if not eligibility.eligible:
        return DecisionBlocker(
            code="not_eligible",
            message=eligibility.reason,
            hint="ask an operator to list you or one of your roles under "
            "`approval_policy.reviewers`",
            forbidden=True,
        )
    return None


def _content_blocker(
    policy: Policy,
    record: StoredRecord,
    events: Sequence[DecisionEvent],
    reviewer: Reviewer,
    expected_digest: str | None,
) -> DecisionBlocker | None:
    """Apply checks 5-8 of the module docstring."""
    reason = approval_blocker(record)
    if reason is not None:
        return DecisionBlocker(
            code="not_approvable",
            message=f"this content cannot be decided: {reason}",
            hint="fix the file at its source; it is re-indexed on the next "
            "poll or push",
        )
    if _is_self(policy, reviewer, record.author):
        return DecisionBlocker(
            code="self_approval",
            message="you are the author of this content and the policy "
            "disallows self-approval",
            hint="ask another eligible reviewer to decide",
            forbidden=True,
        )
    if expected_digest is not None and expected_digest != record.digest:
        return DecisionBlocker(
            code="digest_changed",
            message="the content changed since you loaded it",
            hint="reload the record, review the new content, then decide",
        )
    if any(event.digest == record.digest for event in events):
        return DecisionBlocker(
            code="already_decided",
            message="a decision for this exact content already exists",
            hint="decisions are final per content hash; changed content "
            "gets its own decision",
        )
    return None


def decision_blocker(
    record: StoredRecord,
    events: Sequence[DecisionEvent],
    policy_config: PolicyConfig | None,
    reviewer: Reviewer,
    *,
    expected_digest: str | None = None,
) -> DecisionBlocker | None:
    """
    Tell why *reviewer* cannot decide *record* now, if they cannot.

    :param record: The record row.
    :param events: Every decision event of the record's identity.
    :param policy_config: The approval policy status, or ``None``.
    :param reviewer: The caller.
    :param expected_digest: Digest the caller saw, if sent.
    :returns: The first failing check (module docstring), or ``None``.
    """
    blocker = _policy_blocker(policy_config, reviewer)
    if blocker is not None or policy_config is None:
        return blocker
    policy = policy_config.policy
    if policy is None:  # pragma: no cover - handled by _policy_blocker
        return None
    return _content_blocker(policy, record, events, reviewer, expected_digest)


def _provenance(record: StoredRecord) -> dict[str, str | None]:
    """Describe the decided row at decision time."""
    return {
        "record_id": str(record.id),
        "kind": record.kind.value,
        "source_id": record.source_id,
        "project": record.project,
        "ref": record.ref,
        "path": record.path,
        "source_url": record.source_url,
    }


def record_decision(
    provider: CatalogStoreProvider,
    record_id: uuid.UUID,
    *,
    action: DecisionAction,
    comment: str | None,
    expected_digest: str | None,
    reviewer: Reviewer,
    policy_config: PolicyConfig | None,
) -> DecisionEvent:
    """
    Append an accept/reject decision for a record's current content.

    :param provider: Storage provider.
    :param record_id: Record id.
    :param action: Accepted or rejected.
    :param comment: Optional reviewer comment (blank means none).
    :param expected_digest: Digest the reviewer saw, if sent.
    :param reviewer: The caller.
    :param policy_config: The approval policy status.
    :returns: The stored event.
    :raises NotFoundError: ``record_not_found``.
    :raises ForbiddenError: ``not_eligible`` / ``self_approval``.
    :raises ConflictError: ``policy_missing``, ``approval_not_required``,
        ``not_approvable``, ``digest_changed``, ``already_decided``.
    """
    with provider.unit_of_work() as store:
        record = store.get_record(record_id)
        if record is None:
            raise NotFoundError(
                f"record {record_id} not found", code="record_not_found"
            )
        events = store.list_decisions(record.identity)
        blocker = decision_blocker(
            record,
            events,
            policy_config,
            reviewer,
            expected_digest=expected_digest,
        )
        if blocker is not None:
            raise blocker.to_error()
        policy = policy_config.policy if policy_config else None
        if policy is None or record.adr_uuid is None:  # pragma: no cover
            raise ConflictError("decision refused", code="policy_missing")
        decision = NewDecision(
            identity=record.identity,
            adr_uuid=record.adr_uuid,
            digest=record.digest,
            action=action,
            actor_issuer=reviewer.issuer,
            actor_subject=reviewer.subject,
            actor_display=reviewer.display,
            actor_email=reviewer.email,
            comment=(comment or "").strip() or None,
            policy_id=policy.id,
            policy_version=policy.version,
            provenance=_provenance(record),
        )
        try:
            return store.append_decision(decision)
        except DecisionExistsError as exc:
            raise ConflictError(
                "a decision for this exact content already exists",
                code="already_decided",
                hint="reload the record to see the recorded decision",
            ) from exc
