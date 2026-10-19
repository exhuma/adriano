"""
Source-registration queries of the PostgreSQL store.

Public API: :func:`sync_registrations`, :func:`get_registration`,
:func:`list_registrations`, :func:`update_poll_status`.
"""

import datetime
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Table, case, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.frontmatter import JsonValue
from app.storage.port import PollStatus, Registration, RegistrationConfig
from app.storage.postgres import convert
from app.storage.postgres.models import SourceRegistrationRow

REGISTRATION: Table = SourceRegistrationRow.__table__  # type: ignore[assignment]

#: ``config_error`` set on registrations no longer in the configuration.
REMOVED_FROM_CONFIG = "registration is no longer in catalog.yaml"


def _status_on_sync(enabled: bool) -> Any:
    """
    Compute ``last_status`` for a synced, already stored registration.

    :param enabled: Whether the configured entry is valid.
    :returns: ``'disabled'`` for invalid entries; a previously disabled
        valid entry restarts at ``'never'``; otherwise unchanged.
    """
    if not enabled:
        return PollStatus.DISABLED.value
    return case(
        (
            REGISTRATION.c.last_status == PollStatus.DISABLED.value,
            PollStatus.NEVER.value,
        ),
        else_=REGISTRATION.c.last_status,
    )


def sync_registrations(
    session: Session, registrations: Sequence[RegistrationConfig]
) -> None:
    """
    Make stored registrations match the configuration.

    :param session: Unit-of-work session.
    :param registrations: All configured registrations.
    """
    for item in registrations:
        stmt = insert(REGISTRATION).values(
            id=item.id,
            type=item.type,
            config=dict(item.config),
            enabled=item.enabled,
            config_error=item.config_error,
            last_status=(
                PollStatus.NEVER if item.enabled else PollStatus.DISABLED
            ).value,
        )
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "type": stmt.excluded.type,
                    "config": stmt.excluded.config,
                    "enabled": stmt.excluded.enabled,
                    "config_error": stmt.excluded.config_error,
                    "last_status": _status_on_sync(item.enabled),
                },
            )
        )
    configured = [item.id for item in registrations]
    session.execute(
        update(REGISTRATION)
        .where(REGISTRATION.c.id.not_in(configured))
        .values(
            enabled=False,
            config_error=REMOVED_FROM_CONFIG,
            last_status=PollStatus.DISABLED.value,
        )
    )


def get_registration(session: Session, source_id: str) -> Registration | None:
    """
    Fetch one registration.

    :param session: Unit-of-work session.
    :param source_id: Registration id.
    :returns: The registration, or ``None``.
    """
    row = (
        session.execute(
            select(REGISTRATION).where(REGISTRATION.c.id == source_id)
        )
        .mappings()
        .first()
    )
    return None if row is None else convert.registration(row)


def list_registrations(session: Session) -> list[Registration]:
    """
    List all registrations ordered by id.

    :param session: Unit-of-work session.
    :returns: The registrations.
    """
    rows = session.execute(
        select(REGISTRATION).order_by(REGISTRATION.c.id)
    ).mappings()
    return [convert.registration(row) for row in rows]


def update_poll_status(
    session: Session,
    source_id: str,
    status: PollStatus,
    attempted_at: datetime.datetime,
    error: JsonValue,
) -> None:
    """
    Record the outcome of a poll.

    :param session: Unit-of-work session.
    :param source_id: Registration id.
    :param status: Poll outcome.
    :param attempted_at: When the poll started.
    :param error: Error details, or ``None``.
    :raises LookupError: If the registration does not exist.
    """
    values: dict[str, Any] = {
        "last_attempt_at": attempted_at,
        "last_status": status.value,
        "last_error": error,
    }
    if status is PollStatus.OK:
        values["last_success_at"] = attempted_at
    result = session.execute(
        update(REGISTRATION)
        .where(REGISTRATION.c.id == source_id)
        .values(values)
        .returning(REGISTRATION.c.id)
    )
    if result.first() is None:
        raise LookupError(f"unknown registration {source_id!r}")
