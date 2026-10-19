"""Integration tests for revisions and records in the PostgreSQL store."""

import dataclasses
import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.domain.issues import IssueCode, error
from app.domain.values import Identity, Links
from app.errors import CandidateExistsError
from app.storage.port import RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import make_engine, put_record

U1 = uuid.UUID("0b0c2f4e-1234-4abc-8def-0123456789ab")
U2 = uuid.UUID("1b0c2f4e-1234-4abc-8def-0123456789ab")


def test_revision_is_put_once(provider: PostgresStoreProvider) -> None:
    """Ensure revisions are content-addressed and never overwritten."""
    with provider.unit_of_work() as store:
        assert store.put_revision("sha256-v1:x", "one") is True
        assert store.put_revision("sha256-v1:x", "two") is False
        revision = store.get_revision("sha256-v1:x")
        assert store.get_revision("sha256-v1:missing") is None
    assert revision is not None
    assert revision.content == "one"


def test_upsert_published_tracks_digest_changes(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure the published upsert keeps id and records previous digest."""
    with provider.unit_of_work() as store:
        first = put_record(store, adr_uuid=U1)
        created = store.upsert_published(first)
        same = store.upsert_published(first)
        second = put_record(store, adr_uuid=U1, body="Changed body.")
        changed = store.upsert_published(second)
        row = store.get_record(created.id)
    assert created.created and not created.digest_changed
    assert same.id == created.id
    assert not same.created and not same.digest_changed
    assert changed.id == created.id
    assert changed.digest_changed
    assert changed.previous_digest == first.digest
    assert row is not None
    assert row.kind is RecordState.PUBLISHED
    assert row.digest == second.digest
    assert row.previous_digest == first.digest
    assert row.identity == Identity("central", "platform", str(U1))


def test_record_round_trips_all_fields(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure every written field is read back unchanged."""
    with provider.unit_of_work() as store:
        write = dataclasses.replace(
            put_record(
                store,
                issues=(error(IssueCode.MISSING_UUID, "no uuid"),),
            ),
            links=Links(updates=(U2,)),
            source_url="https://example.com/a.md",
            author="dev@example.com",
        )
        result = store.upsert_published(write)
        row = store.get_record(result.id)
    assert row is not None
    for item in dataclasses.fields(write):
        assert getattr(row, item.name) == getattr(write, item.name)
    assert row.record_key.startswith("src:central/platform/")


def test_candidates_are_keyed_by_ref(provider: PostgresStoreProvider) -> None:
    """Ensure candidates are per ref and coexist with the published row."""
    with provider.unit_of_work() as store:
        published = store.upsert_published(put_record(store, adr_uuid=U1))
        feature = store.upsert_candidate(
            put_record(store, adr_uuid=U1, ref="feature", body="Draft.")
        )
        again = store.upsert_candidate(
            put_record(store, adr_uuid=U1, ref="feature", body="Draft 2.")
        )
        other = store.upsert_candidate(
            put_record(store, adr_uuid=U1, ref="other", body="Alt.")
        )
        siblings = store.list_identity_siblings(
            Identity("central", "platform", str(U1))
        )
    assert again.id == feature.id and again.digest_changed
    assert len({published.id, feature.id, other.id}) == 3
    assert [row.kind for row in siblings] == [
        RecordState.PUBLISHED,
        RecordState.CANDIDATE,
        RecordState.CANDIDATE,
    ]
    assert [row.ref for row in siblings] == ["main", "feature", "other"]


def test_create_candidate_conflict(provider: PostgresStoreProvider) -> None:
    """Ensure create-only candidates signal a conflict and keep the row."""
    with provider.unit_of_work() as store:
        write = put_record(store, adr_uuid=U1, ref="feature")
        created = store.create_candidate(write)
        changed = put_record(store, adr_uuid=U1, ref="feature", body="New.")
        with pytest.raises(CandidateExistsError):
            store.create_candidate(changed)
        row = store.get_record(created.id)
    assert created.created
    assert row is not None and row.digest == write.digest


def test_partial_unique_indexes(
    provider: PostgresStoreProvider, engine: Engine
) -> None:
    """Ensure the partial unique indexes reject duplicates per kind."""
    with provider.unit_of_work() as store:
        result = store.upsert_published(put_record(store, adr_uuid=U1))
    duplicate = text(
        "INSERT INTO record (kind, source_id, project, path, ref, "
        "record_key, digest, metadata, title, title_source, "
        "decision_date_inferred, record_kind, links, rendered_html, "
        "issues) SELECT :kind, source_id, project, path, :ref, "
        "record_key, digest, metadata, title, title_source, "
        "decision_date_inferred, record_kind, links, rendered_html, "
        "issues FROM record WHERE id = :id"
    )
    with engine.begin() as connection:
        # A candidate at the same location as the published row is fine.
        connection.execute(
            duplicate, {"kind": "candidate", "ref": "x", "id": result.id}
        )
    for kind, ref in (("published", "y"), ("candidate", "x")):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                duplicate, {"kind": kind, "ref": ref, "id": result.id}
            )


def test_change_tokens_and_reconcile_delete(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure change tokens list published rows and deletes skip others."""
    with provider.unit_of_work() as store:
        a = store.upsert_published(put_record(store, path="a.md"))
        b = store.upsert_published(
            put_record(store, project="payments", path="b.md")
        )
        cand = store.upsert_candidate(
            put_record(store, adr_uuid=U1, ref="feature")
        )
        all_tokens = store.list_change_tokens("central")
        payments = store.list_change_tokens("central", "payments")
        deleted = store.delete_published([a.id, cand.id])
        assert store.delete_published([]) == 0
        remaining = store.list_change_tokens("central")
        candidate = store.get_record(cand.id)
    assert [(t.project, t.path) for t in all_tokens] == [
        ("payments", "b.md"),
        ("platform", "a.md"),
    ]
    assert all_tokens[1].change_token == "1:1"
    assert [t.id for t in payments] == [b.id]
    assert deleted == 1
    assert [t.id for t in remaining] == [b.id]
    assert candidate is not None


def test_relationship_summaries(provider: PostgresStoreProvider) -> None:
    """Ensure summaries carry identity, UUID and links, filtered by kind."""
    with provider.unit_of_work() as store:
        write = dataclasses.replace(
            put_record(store, adr_uuid=U2), links=Links(obsoletes=(U1,))
        )
        published = store.upsert_published(write)
        store.upsert_candidate(put_record(store, adr_uuid=U1, ref="f"))
        summaries = store.list_relationship_summaries()
        everything = store.list_relationship_summaries(None)
    assert [s.key for s in summaries] == [str(published.id)]
    assert summaries[0].links.obsoletes == (U1,)
    assert summaries[0].adr_uuid == U2
    assert len(everything) == 2


def test_rollback_on_error(provider: PostgresStoreProvider) -> None:
    """Ensure a failing unit of work leaves nothing behind."""
    with pytest.raises(RuntimeError), provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=U1))
        raise RuntimeError("boom")
    with provider.unit_of_work() as store:
        assert store.list_change_tokens("central") == []


def test_data_survives_a_new_engine(engine: Engine) -> None:
    """Ensure committed data is read back through a brand-new engine."""
    first = PostgresStoreProvider(engine)
    with first.unit_of_work() as store:
        result = store.upsert_published(put_record(store, adr_uuid=U1))
    engine.dispose()
    fresh_engine = make_engine()
    try:
        with PostgresStoreProvider(fresh_engine).unit_of_work() as store:
            row = store.get_record(result.id)
    finally:
        fresh_engine.dispose()
    assert row is not None and row.adr_uuid == U1
