"""Integration tests for erratum content and the errata reverse lookup."""

import dataclasses
import datetime
import uuid

from sqlalchemy import Engine, text

from app.domain.approval import DecisionAction
from app.domain.errata import ErratumType
from app.domain.values import Links, RecordKind
from app.storage.port import (
    CatalogStore,
    NewDecision,
    RecordState,
    RecordWrite,
    StoredErratum,
)
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import put_record

TARGET = uuid.UUID("0b0c2f4e-1234-4abc-8def-0123456789ab")
OTHER = uuid.UUID("1b0c2f4e-1234-4abc-8def-0123456789ab")
E1 = uuid.UUID("2b0c2f4e-1234-4abc-8def-0123456789ab")
E2 = uuid.UUID("3b0c2f4e-1234-4abc-8def-0123456789ab")
E3 = uuid.UUID("4b0c2f4e-1234-4abc-8def-0123456789ab")

CONTENT = StoredErratum(
    type=ErratumType.TECHNICAL,
    section="Consequences",
    reported_by="alice@example.com",
    reported_date=datetime.date(2025, 5, 1),
    original_html="<p>says</p>\n",
    corrected_html="<p>should say</p>\n",
    notes_html=None,
)


def erratum_write(
    store: CatalogStore,
    adr_uuid: uuid.UUID,
    target: uuid.UUID,
    *,
    ref: str = "main",
    project: str = "platform",
    content: StoredErratum | None = CONTENT,
) -> RecordWrite:
    """
    Store the revision of a test erratum and build its record write.

    :param store: Store in the current unit of work.
    :param adr_uuid: The erratum's own UUID.
    :param target: UUID of the corrected decision.
    :param ref: Ref.
    :param project: Project path.
    :param content: Stored erratum content.
    :returns: The record write (not yet upserted).
    """
    base = put_record(
        store,
        adr_uuid=adr_uuid,
        project=project,
        ref=ref,
        path=f"doc/decisions/errata/{adr_uuid}.md",
        title=f"Erratum {adr_uuid}",
    )
    return dataclasses.replace(
        base,
        record_kind=RecordKind.ERRATUM,
        links=Links(corrects=target),
        erratum=content,
    )


def test_erratum_round_trips_for_published_and_candidate(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure erratum content is stored and read back for both kinds."""
    sparse = StoredErratum(
        type=None,
        section=None,
        reported_by=None,
        reported_date=None,
        original_html=None,
        corrected_html="",
        notes_html=None,
    )
    with provider.unit_of_work() as store:
        store.upsert_published(erratum_write(store, E1, TARGET))
        store.upsert_candidate(
            erratum_write(store, E2, TARGET, ref="fix", content=sparse)
        )
        published_row = store.get_published(E1)
        candidate_row = store.get_candidate(E2, "fix")
    assert published_row is not None and candidate_row is not None
    assert published_row.erratum == CONTENT
    assert candidate_row.erratum == sparse
    assert candidate_row.kind is RecordState.CANDIDATE


def test_decision_rows_store_sql_null(
    provider: PostgresStoreProvider, engine: Engine
) -> None:
    """Ensure decisions have no erratum content, as SQL NULL not JSON."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=TARGET))
        row = store.get_published(TARGET)
    assert row is not None and row.erratum is None
    with engine.connect() as connection:
        is_null = connection.execute(
            text("SELECT erratum IS NULL FROM record WHERE adr_uuid = :id"),
            {"id": TARGET},
        ).scalar_one()
    assert is_null is True


def test_list_errata_for_returns_published_and_candidates(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure the reverse lookup returns every erratum of one target."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=TARGET))
        store.upsert_candidate(
            erratum_write(store, E2, TARGET, ref="fix", project="apps")
        )
        store.upsert_published(erratum_write(store, E1, TARGET))
        store.upsert_published(erratum_write(store, E3, OTHER))
        rows = store.list_errata_for(TARGET)
        other = store.list_errata_for(OTHER)
        none = store.list_errata_for(uuid.uuid4())
    assert [(r.adr_uuid, r.kind) for r in rows] == [
        (E1, RecordState.PUBLISHED),
        (E2, RecordState.CANDIDATE),
    ]
    first = rows[0]
    assert first.erratum == CONTENT
    assert first.title == f"Erratum {E1}"
    assert rows[1].ref == "fix" and rows[1].project == "apps"
    assert [r.adr_uuid for r in other] == [E3]
    assert none == []


def test_list_errata_for_ignores_decisions(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure decisions never appear, whatever their links say."""
    with provider.unit_of_work() as store:
        decision = dataclasses.replace(
            put_record(store, adr_uuid=E1), links=Links(updates=(TARGET,))
        )
        store.upsert_published(decision)
        rows = store.list_errata_for(TARGET)
    assert rows == []


def _decision(write: RecordWrite) -> NewDecision:
    """
    Build an acceptance of a record write's digest.

    :param write: The record write.
    :returns: The decision.
    """
    return NewDecision(
        adr_uuid=write.adr_uuid,
        digest=write.digest,
        action=DecisionAction.ACCEPTED,
        actor_issuer="iss",
        actor_subject="sub",
        actor_display=None,
        actor_email=None,
        comment=None,
        policy_id="global",
        policy_version=1,
    )


def test_list_decisions_for_reads_several_uuids_at_once(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure batched decisions return exactly the given UUIDs."""
    with provider.unit_of_work() as store:
        writes = [
            put_record(store, adr_uuid=adr_uuid, path=f"{adr_uuid}.md")
            for adr_uuid in (E1, E2, E3)
        ]
        for write in writes:
            store.upsert_published(write)
            store.append_decision(_decision(write))

        events = store.list_decisions_for([w.adr_uuid for w in writes[:2]])
        empty = store.list_decisions_for([])

    assert {event.adr_uuid for event in events} == {E1, E2}
    assert empty == []
