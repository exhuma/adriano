"""
The approval decision log.

Part of the :class:`app.storage.port.CatalogStore` protocol, split by
concern to keep modules small. Import :class:`ApprovalStore` only to compose
the store; services depend on :mod:`app.storage.port`.

Public API: :class:`ApprovalStore`.
"""

import uuid
from collections.abc import Collection
from typing import Protocol

from app.storage.approval_values import DecisionEvent, NewDecision


class ApprovalStore(Protocol):
    """The approval decision log."""

    def append_decision(self, decision: NewDecision) -> DecisionEvent:
        """
        Append a decision event; the server sets id and timestamp.

        :param decision: The decision.
        :returns: The stored event.
        :raises app.errors.DecisionExistsError: If the ADR already has
            a decision for the digest.
        """
        ...

    def list_decisions(self, adr_uuid: uuid.UUID) -> list[DecisionEvent]:
        """
        List all decision events of an ADR, any digest.

        :param adr_uuid: The ADR's UUID.
        :returns: Events, oldest first.
        """
        ...

    def list_decisions_for(
        self, uuids: Collection[uuid.UUID]
    ) -> list[DecisionEvent]:
        """
        List all decision events of several ADRs in one query.

        :param uuids: ADR UUIDs.
        :returns: Events of all of them, oldest first; group them by
            :attr:`~app.storage.port.DecisionEvent.adr_uuid`.
        """
        ...
