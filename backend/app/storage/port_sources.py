"""
Registrations and intake runs of a unit of work.

Part of the :class:`app.storage.port.CatalogStore` protocol, split by
concern to keep modules small. Import :class:`SourceStore` only to compose
the store; services depend on :mod:`app.storage.port`.

Public API: :class:`SourceStore`.
"""

import datetime
import uuid
from collections.abc import Sequence
from typing import Protocol

from app.domain.frontmatter import JsonValue
from app.storage.intake_values import IntakeRun
from app.storage.values import (
    IntakeKind,
    IntakeStatus,
    PollStatus,
    Registration,
    RegistrationConfig,
)


class SourceStore(Protocol):
    """Registrations and intake runs of a unit of work."""

    def sync_registrations(
        self, registrations: Sequence[RegistrationConfig]
    ) -> None:
        """
        Make stored registrations match the configuration.

        Listed registrations are inserted or updated; an invalid one gets
        status ``disabled``, and a re-enabled one leaves ``disabled`` for
        ``never``. Registrations missing from the list are disabled,
        never deleted.

        :param registrations: All configured registrations.
        """
        ...

    def get_registration(self, source_id: str) -> Registration | None:
        """
        Fetch one registration.

        :param source_id: Registration id.
        :returns: The registration, or ``None``.
        """
        ...

    def list_registrations(self) -> list[Registration]:
        """
        List all registrations, enabled or not, ordered by id.

        :returns: The registrations.
        """
        ...

    def update_poll_status(
        self,
        source_id: str,
        status: PollStatus,
        attempted_at: datetime.datetime,
        error: JsonValue = None,
    ) -> None:
        """
        Record the outcome of a poll.

        ``last_success_at`` is set to *attempted_at* only for
        :attr:`PollStatus.OK`.

        :param source_id: Registration id.
        :param status: Poll outcome.
        :param attempted_at: When the poll started.
        :param error: Error details, ``None`` on success.
        """
        ...

    def start_intake_run(
        self,
        source_id: str,
        kind: IntakeKind,
        *,
        identity: JsonValue = None,
        delivery_id: str | None = None,
    ) -> IntakeRun:
        """
        Record the start of an intake run.

        :param source_id: Registration id as requested.
        :param kind: Poll or push.
        :param identity: Who triggered the run (no secrets).
        :param delivery_id: Push delivery id, if any.
        :returns: The running run.
        :raises app.errors.DeliveryExistsError: If *delivery_id* was
            already used for *source_id*.
        """
        ...

    def finish_intake_run(
        self,
        run_id: uuid.UUID,
        status: IntakeStatus,
        *,
        counts: JsonValue = None,
        errors: JsonValue = None,
    ) -> IntakeRun:
        """
        Record the end of an intake run.

        :param run_id: Run id.
        :param status: Final status.
        :param counts: Outcome counters.
        :param errors: Error details.
        :returns: The finished run.
        :raises LookupError: If the run does not exist.
        """
        ...

    def find_intake_run(
        self, source_id: str, delivery_id: str
    ) -> IntakeRun | None:
        """
        Find the run of an earlier push delivery.

        :param source_id: Registration id.
        :param delivery_id: Push delivery id.
        :returns: The run, or ``None``.
        """
        ...
