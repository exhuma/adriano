"""
Decision-event and intake-run queries of the PostgreSQL store.

Decision uniqueness per (identity, digest) is enforced by
``uq_decision_event_identity_digest``; inserts use ``ON CONFLICT DO
NOTHING`` so a conflict (including a concurrent one) is reported as a
domain error without aborting the surrounding transaction.

Public API: :func:`append_decision`, :func:`list_decisions`,
:func:`list_decisions_for`, :func:`start_intake_run`, :func:`finish_intake_run`,
:func:`find_intake_run`.
"""

import uuid
from collections.abc import Collection

from sqlalchemy import Table, func, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.frontmatter import JsonValue
from app.domain.values import Identity
from app.errors import DecisionExistsError, DeliveryExistsError
from app.storage.port import (
    DecisionEvent,
    IntakeKind,
    IntakeRun,
    IntakeStatus,
    NewDecision,
)
from app.storage.postgres import convert
from app.storage.postgres.models import DecisionEventRow, IntakeRunRow

DECISION: Table = DecisionEventRow.__table__  # type: ignore[assignment]
INTAKE: Table = IntakeRunRow.__table__  # type: ignore[assignment]


def append_decision(session: Session, decision: NewDecision) -> DecisionEvent:
    """
    Append a decision event.

    ``created_at`` is the server's ``clock_timestamp()`` so events keep
    their real order even within one transaction.

    :param session: Unit-of-work session.
    :param decision: The decision.
    :returns: The stored event.
    :raises DecisionExistsError: If (identity, digest) is decided.
    """
    identity = decision.identity
    stmt = (
        insert(DECISION)
        .values(
            source_id=identity.source_id,
            project=identity.project,
            record_key=identity.record_key,
            adr_uuid=decision.adr_uuid,
            digest=decision.digest,
            action=decision.action.value,
            actor_issuer=decision.actor_issuer,
            actor_subject=decision.actor_subject,
            actor_display=decision.actor_display,
            actor_email=decision.actor_email,
            comment=decision.comment,
            policy_id=decision.policy_id,
            policy_version=decision.policy_version,
            provenance=dict(decision.provenance),
            created_at=func.clock_timestamp(),
        )
        .on_conflict_do_nothing(constraint="uq_decision_event_identity_digest")
        .returning(*DECISION.c)
    )
    row = session.execute(stmt).mappings().first()
    if row is None:
        raise DecisionExistsError(
            f"{identity} already has a decision for {decision.digest}"
        )
    return convert.decision_event(row)


def list_decisions(session: Session, identity: Identity) -> list[DecisionEvent]:
    """
    List all decision events of an identity.

    :param session: Unit-of-work session.
    :param identity: Logical identity.
    :returns: Events, oldest first (ties by id).
    """
    stmt = (
        select(DECISION)
        .where(
            DECISION.c.source_id == identity.source_id,
            DECISION.c.project == identity.project,
            DECISION.c.record_key == identity.record_key,
        )
        .order_by(DECISION.c.created_at, DECISION.c.id)
    )
    rows = session.execute(stmt).mappings()
    return [convert.decision_event(row) for row in rows]


def list_decisions_for(
    session: Session, identities: Collection[Identity]
) -> list[DecisionEvent]:
    """
    List the decision events of several identities in one query.

    :param session: Unit-of-work session.
    :param identities: Logical identities; empty means no query.
    :returns: Events of all of them, oldest first (ties by id).
    """
    if not identities:
        return []
    keys = [(i.source_id, i.project, i.record_key) for i in identities]
    stmt = (
        select(DECISION)
        .where(
            tuple_(
                DECISION.c.source_id,
                DECISION.c.project,
                DECISION.c.record_key,
            ).in_(keys)
        )
        .order_by(DECISION.c.created_at, DECISION.c.id)
    )
    rows = session.execute(stmt).mappings()
    return [convert.decision_event(row) for row in rows]


def start_intake_run(
    session: Session,
    source_id: str,
    kind: IntakeKind,
    identity: JsonValue,
    delivery_id: str | None,
) -> IntakeRun:
    """
    Record the start of an intake run.

    ``started_at`` uses ``clock_timestamp()`` so runs inside a long unit
    of work get real times.

    :param session: Unit-of-work session.
    :param source_id: Registration id as requested.
    :param kind: Poll or push.
    :param identity: Who triggered the run.
    :param delivery_id: Push delivery id, if any.
    :returns: The running run.
    :raises DeliveryExistsError: If the delivery id was used before.
    """
    stmt = (
        insert(INTAKE)
        .values(
            source_id=source_id,
            kind=kind.value,
            identity=identity,
            delivery_id=delivery_id,
            started_at=func.clock_timestamp(),
            status=IntakeStatus.RUNNING.value,
        )
        .on_conflict_do_nothing(
            index_elements=["source_id", "delivery_id"],
            index_where=text("delivery_id IS NOT NULL"),
        )
        .returning(*INTAKE.c)
    )
    row = session.execute(stmt).mappings().first()
    if row is None:
        raise DeliveryExistsError(
            f"delivery {delivery_id!r} for {source_id!r} was already received"
        )
    return convert.intake_run(row)


def finish_intake_run(
    session: Session,
    run_id: uuid.UUID,
    status: IntakeStatus,
    counts: JsonValue,
    errors: JsonValue,
) -> IntakeRun:
    """
    Record the end of an intake run.

    :param session: Unit-of-work session.
    :param run_id: Run id.
    :param status: Final status.
    :param counts: Outcome counters.
    :param errors: Error details.
    :returns: The finished run.
    :raises LookupError: If the run does not exist.
    """
    stmt = (
        update(INTAKE)
        .where(INTAKE.c.id == run_id)
        .values(
            status=status.value,
            counts=counts,
            errors=errors,
            finished_at=func.clock_timestamp(),
        )
        .returning(*INTAKE.c)
    )
    row = session.execute(stmt).mappings().first()
    if row is None:
        raise LookupError(f"unknown intake run {run_id}")
    return convert.intake_run(row)


def find_intake_run(
    session: Session, source_id: str, delivery_id: str
) -> IntakeRun | None:
    """
    Find the run of an earlier push delivery.

    :param session: Unit-of-work session.
    :param source_id: Registration id.
    :param delivery_id: Push delivery id.
    :returns: The run, or ``None``.
    """
    stmt = select(INTAKE).where(
        INTAKE.c.source_id == source_id,
        INTAKE.c.delivery_id == delivery_id,
    )
    row = session.execute(stmt).mappings().first()
    return None if row is None else convert.intake_run(row)
