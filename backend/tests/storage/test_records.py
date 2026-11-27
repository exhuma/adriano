"""Integration tests for revisions and records in the PostgreSQL store."""

import dataclasses
import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.domain.issues import IssueCode, error
from app.domain.values import Links
from app.errors import CandidateExistsError
from app.storage.port import ChangeTokenEntry, RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import make_engine, put_record

U1 = uuid.UUID("0b0c2f4e-1234-4abc-8def-0123456789ab")
U2 = uuid.UUID("1b0c2f4e-1234-4abc-8def-0123456789ab")
U3 = uuid.UUID("2b0c2f4e-1234-4abc-8def-0123456789ab")
U4 = uuid.UUID("3b0c2f4e-1234-4abc-8def-0123456789ab")


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
    """Ensure the published upsert keys by UUID and keeps digest history."""
    with provider.unit_of_work() as store:
        first = put_record(store, adr_uuid=U1)
        created = store.upsert_published(first)
        same = store.upsert_published(first)
        second = put_record(store, adr_uuid=U1, body="Changed body.")
        changed = store.upsert_published(second)
        row = store.get_published(U1)
    assert created.created and not created.digest_changed
    assert not same.created and not same.digest_changed
    assert changed.digest_changed and not changed.moved
    assert changed.previous_digest == first.digest
    assert row is not None
    assert row.kind is RecordState.PUBLISHED
    assert row.digest == second.digest
    assert row.previous_digest == first.digest


def test_published_uuid_is_unique_across_sources_and_projects(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure one UUID has one published row, wherever its file lives."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=U1))
        moved = store.upsert_published(
            put_record(
                store,
                adr_uuid=U1,
                source_id="other",
                project="payments",
                path="doc/decisions/moved.md",
            )
        )
        central = store.list_change_tokens("central")
        other = store.list_change_tokens("other")
    assert moved.moved and not moved.created and not moved.digest_changed
    assert central == []
    assert [(e.adr_uuid, e.project, e.path) for e in other] == [
        (U1, "payments", "doc/decisions/moved.md")
    ]


def test_move_keeps_first_seen_and_digest_history(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure moving a row keeps ``first_seen_at`` and its history."""
    with provider.unit_of_work() as store:
        first = put_record(store, adr_uuid=U1)
        store.upsert_published(first)
    with provider.unit_of_work() as store:
        before = store.get_published(U1)
        store.upsert_published(
            put_record(
                store,
                adr_uuid=U1,
                project="payments",
                path="elsewhere.md",
                ref="develop",
                body="Edited while moving.",
            )
        )
        after = store.get_published(U1)
    assert before is not None and after is not None
    assert after.first_seen_at == before.first_seen_at
    assert after.previous_digest == first.digest
    assert (after.project, after.path, after.ref) == (
        "payments",
        "elsewhere.md",
        "develop",
    )


def test_record_round_trips_all_fields(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure every written field is read back unchanged."""
    with provider.unit_of_work() as store:
        write = dataclasses.replace(
            put_record(
                store,
                adr_uuid=U1,
                issues=(error(IssueCode.BAD_DATE, "bad date"),),
            ),
            links=Links(updates=(U2,)),
            source_url="https://example.com/a.md",
            author="dev@example.com",
        )
        store.upsert_published(write)
        row = store.get_published(U1)
    assert row is not None
    for item in dataclasses.fields(write):
        assert getattr(row, item.name) == getattr(write, item.name)


def test_candidates_are_keyed_by_uuid_and_ref(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure candidates are per UUID and ref, next to the published row."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=U1))
        feature = store.upsert_candidate(
            put_record(store, adr_uuid=U1, ref="feature", body="Draft.")
        )
        again = store.upsert_candidate(
            put_record(store, adr_uuid=U1, ref="feature", body="Draft 2.")
        )
        store.upsert_candidate(
            put_record(store, adr_uuid=U1, ref="other", body="Alt.")
        )
        rows = store.list_records(U1)
        candidate = store.get_candidate(U1, "feature")
        assert store.get_candidate(U1, "missing") is None
        assert store.get_candidate(U2, "feature") is None
    assert feature.created
    assert again.digest_changed and not again.created
    assert [(row.kind, row.ref) for row in rows] == [
        (RecordState.PUBLISHED, "main"),
        (RecordState.CANDIDATE, "feature"),
        (RecordState.CANDIDATE, "other"),
    ]
    assert candidate is not None and candidate.title == "A decision"


def test_create_candidate_conflict(provider: PostgresStoreProvider) -> None:
    """Ensure create-only candidates signal a conflict and keep the row."""
    with provider.unit_of_work() as store:
        write = put_record(store, adr_uuid=U1, ref="feature")
        created = store.create_candidate(write)
        changed = put_record(store, adr_uuid=U1, ref="feature", body="New.")
        with pytest.raises(CandidateExistsError):
            store.create_candidate(changed)
        row = store.get_candidate(U1, "feature")
    assert created.created
    assert row is not None and row.digest == write.digest


def test_keys_reject_duplicates(
    provider: PostgresStoreProvider, engine: Engine
) -> None:
    """Ensure one published row per UUID and one candidate per ref."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=U1))
    duplicate = text(
        "INSERT INTO record (adr_uuid, kind, ref, source_id, project, path, "
        "digest, metadata, title, title_source, decision_date_inferred, "
        "record_kind, links, rendered_html, issues) "
        "SELECT adr_uuid, :kind, :ref, source_id, 'p2', 'x.md', digest, "
        "metadata, title, title_source, decision_date_inferred, "
        "record_kind, links, rendered_html, issues FROM record "
        "WHERE adr_uuid = :uuid AND kind = 'published'"
    )
    with engine.begin() as connection:
        # A candidate of the same UUID is fine.
        connection.execute(
            duplicate, {"kind": "candidate", "ref": "x", "uuid": U1}
        )
    for kind, ref in (("published", "y"), ("candidate", "x")):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                duplicate, {"kind": kind, "ref": ref, "uuid": U1}
            )


def test_change_tokens_and_reconcile_delete(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure change tokens list published rows and deletes skip others."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=U1, path="a.md"))
        store.upsert_published(
            put_record(store, adr_uuid=U2, project="payments", path="b.md")
        )
        store.upsert_candidate(put_record(store, adr_uuid=U1, ref="feature"))
        all_tokens = store.list_change_tokens("central")
        payments = store.list_change_tokens("central", "payments")
        deleted = store.delete_published([all_tokens[1]])
        assert store.delete_published([]) == 0
        remaining = store.list_change_tokens("central")
        candidate = store.get_candidate(U1, "feature")
    assert [(t.project, t.path) for t in all_tokens] == [
        ("payments", "b.md"),
        ("platform", "a.md"),
    ]
    assert all_tokens[1].change_token == "1:1"
    assert [t.adr_uuid for t in payments] == [U2]
    assert deleted == 1
    assert [t.adr_uuid for t in remaining] == [U2]
    assert candidate is not None


def test_delete_and_token_refresh_are_guarded_by_location(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure a row that moved away is neither deleted nor touched."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=U1, path="a.md"))
        [stale] = store.list_change_tokens("central")
        store.upsert_published(
            put_record(store, adr_uuid=U1, source_id="other", path="a.md")
        )
        refreshed = store.set_change_token(stale, "new")
        deleted = store.delete_published([stale])
        [moved] = store.list_published_entries([U1, U2])
    assert (refreshed, deleted) == (False, 0)
    assert moved.source_id == "other"
    assert moved.change_token == "1:1"


def test_set_change_token_rewrites_the_token(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure an unchanged file's new token is stored."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=U1))
        [entry] = store.list_change_tokens("central")
        assert store.set_change_token(entry, "2:2")
        [after] = store.list_change_tokens("central")
    assert after.change_token == "2:2"
    assert after.digest == entry.digest


def test_relationship_candidates_match_targets_and_inbound_links(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure related rows are the targets and rows linking back."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=U1, path="1.md"))
        store.upsert_published(put_record(store, adr_uuid=U2, path="2.md"))
        store.upsert_published(
            dataclasses.replace(
                put_record(store, adr_uuid=U3, path="3.md"),
                links=Links(updates=(U1,)),
            )
        )
        store.upsert_published(
            dataclasses.replace(
                put_record(store, adr_uuid=U4, path="4.md"),
                links=Links(corrects=U1),
            )
        )
        related = store.list_relationship_candidates(U1, [U2])
    assert [s.adr_uuid for s in related] == sorted([U2, U3, U4])
    assert {s.adr_uuid: s.links for s in related}[U3].updates == (U1,)


def test_relationship_candidates_exclude_candidates_and_self(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure only other published ADRs are returned."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=U1))
        store.upsert_candidate(
            dataclasses.replace(
                put_record(store, adr_uuid=U2, ref="feature", path="d.md"),
                links=Links(updates=(U1,)),
            )
        )
        related = store.list_relationship_candidates(U1, [U1])
    assert related == []


def test_published_titles(provider: PostgresStoreProvider) -> None:
    """Ensure titles come from published rows only."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=U1, title="One"))
        store.upsert_candidate(
            put_record(store, adr_uuid=U2, ref="f", title="Draft")
        )
        titles = store.published_titles({U1, U2, U3})
        assert store.published_titles(set()) == {}
    assert titles == {U1: "One"}


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
        store.upsert_published(put_record(store, adr_uuid=U1))
    engine.dispose()
    fresh_engine = make_engine()
    try:
        with PostgresStoreProvider(fresh_engine).unit_of_work() as store:
            row = store.get_published(U1)
    finally:
        fresh_engine.dispose()
    assert row is not None and row.adr_uuid == U1


def test_entries_carry_their_location() -> None:
    """Ensure an entry's location is its source, project and path."""
    entry = ChangeTokenEntry(
        adr_uuid=U1,
        source_id="central",
        project="platform",
        path="a.md",
        change_token=None,
        digest="d",
    )

    assert str(entry.location) == "central/platform/a.md"
