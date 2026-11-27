"""
Value types of the approval decision log, crossing the storage port.

Plain frozen dataclasses, independent of any ORM; kept apart from
:mod:`app.storage.values` only to keep modules small. Import them
through :mod:`app.storage.port`, which re-exports them.

Public API: :class:`NewDecision`, :class:`DecisionEvent`.
"""

import datetime
import uuid
from dataclasses import dataclass, field

from app.domain.approval import (
    DecisionAction,
    DecisionEventView,
)
from app.storage.values import JsonObject


@dataclass(frozen=True, slots=True, kw_only=True)
class NewDecision:
    """
    A decision to append.

    :param adr_uuid: UUID of the decided ADR.
    :param digest: Digest of the decided content.
    :param action: Accepted or rejected.
    :param actor_issuer: Reviewer token issuer.
    :param actor_subject: Reviewer token subject.
    :param actor_display: Reviewer display name, if known.
    :param actor_email: Reviewer verified email, if known.
    :param comment: Optional reviewer comment.
    :param policy_id: Applied policy id.
    :param policy_version: Applied policy version.
    :param provenance: Historical snapshot of the decided row: kind,
        source, project, ref, path and source URL at decision time.
    """

    adr_uuid: uuid.UUID
    digest: str
    action: DecisionAction
    actor_issuer: str
    actor_subject: str
    actor_display: str | None
    actor_email: str | None
    comment: str | None
    policy_id: str
    policy_version: int
    provenance: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionEvent(NewDecision):
    """
    A stored, append-only decision event.

    :param id: Stable event id.
    :param created_at: Server timestamp.
    """

    id: uuid.UUID
    created_at: datetime.datetime

    def as_view(self) -> DecisionEventView:
        """
        Convert to the domain view used by approval evaluation.

        :returns: The event view.
        """
        return DecisionEventView(
            id=str(self.id),
            digest=self.digest,
            action=self.action,
            created_at=self.created_at,
        )
