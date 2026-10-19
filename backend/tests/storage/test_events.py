"""Integration tests for decision events and intake runs."""

import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.domain.approval import DecisionAction
from app.domain.values import Identity
from app.errors import DecisionExistsError, DeliveryExistsError
from app.storage.port import (
    CatalogStore,
    DecisionEvent,
    IntakeKind,
    IntakeStatus,
    NewDecision,
)
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import put_record

U1 = uuid.UUID("0b0c2f4e-1234-4abc-8def-0123456789ab")
IDENTITY = Identity("central", "platform", str(U1))


def decide(
    store: CatalogStore,
    digest: str,
    action: DecisionAction = DecisionAction.ACCEPTED,
    identity: Identity = IDENTITY,
) -> DecisionEvent:
    """
    Append a decision with fixed reviewer and policy fields.

    :param store: Store in the current unit of work.
    :param digest: Decided digest.
    :param action: Accepted or rejected.
    :param identity: Decided identity.
    :returns: The stored event.
    """
    return store.append_decision(
        NewDecision(
            identity=identity,
            adr_uuid=U1,
            digest=digest,
            action=action,
            actor_issuer="https://idp.example.com",
            actor_subject="subject-123",
            actor_display="Rev Iewer",
            actor_email="rev@example.com",
            comment="looks good",
            policy_id="global",
            policy_version=1,
            provenance={"ref": "main"},
        )
    )


def test_append_and_list_decisions(provider: PostgresStoreProvider) -> None:
    """Ensure decisions are stored with server id/time and listed."""
    with provider.unit_of_work() as store:
        first = put_record(store, adr_uuid=U1)
        second = put_record(store, adr_uuid=U1, body="v2")
        accepted = decide(store, first.digest)
        rejected = decide(store, second.digest, DecisionAction.REJECTED)
        decide(store, first.digest, identity=Identity("other", "p", str(U1)))
    with provider.unit_of_work() as store:
        events = store.list_decisions(IDENTITY)
    assert [event.id for event in events] == [accepted.id, rejected.id]
    assert events[0].identity == IDENTITY
    assert events[0].provenance == {"ref": "main"}
    assert events[0].comment == "looks good"
    view = events[1].as_view()
    assert view.action is DecisionAction.REJECTED
    assert view.digest == second.digest
    assert view.id == str(rejected.id)


def test_second_decision_for_digest_is_refused(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure one decision per identity and digest; the UoW survives."""
    with provider.unit_of_work() as store:
        write = put_record(store, adr_uuid=U1)
        decide(store, write.digest)
        with pytest.raises(DecisionExistsError):
            decide(store, write.digest, DecisionAction.REJECTED)
        assert len(store.list_decisions(IDENTITY)) == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE decision_event SET comment = 'tampered'",
        "DELETE FROM decision_event",
        "UPDATE decision_event SET comment = 'x' WHERE false",
        "TRUNCATE decision_event",
        "TRUNCATE revision CASCADE",
    ],
)
def test_decision_events_are_append_only(
    provider: PostgresStoreProvider, engine: Engine, statement: str
) -> None:
    """Ensure UPDATE, DELETE and TRUNCATE on decision_event fail."""
    with provider.unit_of_work() as store:
        decide(store, put_record(store, adr_uuid=U1).digest)
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(text(statement))
    with provider.unit_of_work() as store:
        events = store.list_decisions(IDENTITY)
    assert [event.comment for event in events] == ["looks good"]


def test_intake_run_lifecycle(provider: PostgresStoreProvider) -> None:
    """Ensure runs are started, finished and found by delivery id."""
    with provider.unit_of_work() as store:
        run = store.start_intake_run(
            "central",
            IntakeKind.PUSH,
            identity={"token": "push-1"},
            delivery_id="d-1",
        )
        assert run.status is IntakeStatus.RUNNING
        assert run.finished_at is None
        done = store.finish_intake_run(
            run.id, IntakeStatus.OK, counts={"created": 1}
        )
        poll = store.start_intake_run("unknown-source", IntakeKind.POLL)
    with provider.unit_of_work() as store:
        found = store.find_intake_run("central", "d-1")
        missing = store.find_intake_run("other", "d-1")
    assert done.status is IntakeStatus.OK
    assert done.finished_at is not None
    assert done.finished_at >= done.started_at
    assert done.counts == {"created": 1}
    assert done.errors is None
    assert poll.delivery_id is None
    assert found == done
    assert missing is None


def test_duplicate_delivery_is_refused(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure a delivery id is unique per registration only."""
    with provider.unit_of_work() as store:
        store.start_intake_run("central", IntakeKind.PUSH, delivery_id="d")
        store.start_intake_run("other", IntakeKind.PUSH, delivery_id="d")
        store.start_intake_run("central", IntakeKind.POLL)
        store.start_intake_run("central", IntakeKind.POLL)
        with pytest.raises(DeliveryExistsError):
            store.start_intake_run("central", IntakeKind.PUSH, delivery_id="d")


def test_finish_unknown_run(provider: PostgresStoreProvider) -> None:
    """Ensure finishing an unknown run raises LookupError."""
    with provider.unit_of_work() as store, pytest.raises(LookupError):
        store.finish_intake_run(uuid.uuid4(), IntakeStatus.FAILED)
