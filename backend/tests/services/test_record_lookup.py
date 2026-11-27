"""Tests for addressing a record by ADR UUID and ref."""

import dataclasses
import uuid

from app.services.record_lookup import RecordAddress, find_record
from app.storage.port import RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import put_record

X = uuid.UUID("6a1f0000-0000-4000-8000-000000000001")


def test_published_row_is_the_default(provider: PostgresStoreProvider) -> None:
    """Ensure no ref picks the published row, a ref its candidate."""
    with provider.unit_of_work() as store:
        store.upsert_published(put_record(store, adr_uuid=X))
        store.upsert_candidate(put_record(store, adr_uuid=X, ref="feature"))
        default = find_record(store, RecordAddress(X))
        candidate = find_record(store, RecordAddress(X, "feature"))
        by_published_ref = find_record(store, RecordAddress(X, "main"))
        missing = find_record(store, RecordAddress(X, "nope"))
    assert default is not None and default.kind is RecordState.PUBLISHED
    assert candidate is not None and candidate.kind is RecordState.CANDIDATE
    assert by_published_ref is not None
    assert by_published_ref.kind is RecordState.PUBLISHED
    assert missing is None


def test_unpublished_adr_shows_its_newest_candidate(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure an ADR with candidates only is found by its UUID."""
    with provider.unit_of_work() as store:
        older = put_record(store, adr_uuid=X, ref="a", title="Older")
        store.upsert_candidate(older)
    with provider.unit_of_work() as store:
        newer = dataclasses.replace(
            put_record(store, adr_uuid=X, ref="b", body="Newer."),
            title="Newer",
        )
        store.upsert_candidate(newer)
        found = find_record(store, RecordAddress(X))
        nothing = find_record(store, RecordAddress(uuid.uuid4()))
    assert found is not None and found.title == "Newer"
    assert nothing is None
