"""Integration tests for the not-indexed list in the PostgreSQL store."""

import dataclasses
import uuid

from sqlalchemy import Engine, text

from app.domain.issues import IssueCode, error
from app.storage.port import IntakeKind, NotIndexedKey, NotIndexedWrite
from app.storage.postgres.store import PostgresStoreProvider

KEY = NotIndexedKey("central", "platform", "doc/decisions/a.md", "main")
HOLDER = uuid.UUID("0b0c2f4e-1234-4abc-8def-0123456789ab")


def entry(
    key: NotIndexedKey = KEY,
    origin: IntakeKind = IntakeKind.POLL,
    code: IssueCode = IssueCode.MISSING_UUID,
    **kwargs: object,
) -> NotIndexedWrite:
    """
    Build a not-indexed entry.

    :param key: Its key.
    :param origin: Poll or push.
    :param code: The reason code.
    :param kwargs: Further :class:`NotIndexedWrite` fields.
    :returns: The entry.
    """
    return NotIndexedWrite(
        key=key,
        origin=origin,
        reasons=(error(code, f"{code.value} here"),),
        **kwargs,  # type: ignore[arg-type]
    )


def test_entry_round_trips(provider: PostgresStoreProvider) -> None:
    """Ensure every written field is read back unchanged."""
    write = entry(
        code=IssueCode.DUPLICATE_UUID,
        digest="sha256-v1:abc",
        holder_uuid=HOLDER,
        change_token="t1",
        source_url="https://example.com/a.md",
    )
    with provider.unit_of_work() as store:
        store.put_revision("sha256-v1:abc", "content")
        store.put_not_indexed(write)
        [stored] = store.list_not_indexed()
    for field in dataclasses.fields(NotIndexedWrite):
        assert getattr(stored, field.name) == getattr(write, field.name)
    assert stored.first_seen_at == stored.last_seen_at


def test_rewrite_keeps_first_seen(
    provider: PostgresStoreProvider, engine: Engine
) -> None:
    """Ensure a rewrite at the same key keeps ``first_seen_at``."""
    with provider.unit_of_work() as store:
        store.put_not_indexed(entry())
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE not_indexed SET first_seen_at = '2020-01-01', "
                "last_seen_at = '2020-01-01'"
            )
        )
    with provider.unit_of_work() as store:
        store.put_not_indexed(entry(code=IssueCode.BAD_YAML))
        [stored] = store.list_not_indexed()
    assert stored.first_seen_at.year == 2020
    assert stored.last_seen_at.year > 2020
    assert [r.code for r in stored.reasons] == [IssueCode.BAD_YAML]


def test_entries_are_keyed_by_location_and_ref(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure refs, sources and origins are listed and filtered apart."""
    other_ref = dataclasses.replace(KEY, ref="dev")
    other_source = dataclasses.replace(KEY, source_id="other")
    with provider.unit_of_work() as store:
        store.put_not_indexed(entry())
        store.put_not_indexed(entry(other_ref, IntakeKind.PUSH))
        store.put_not_indexed(entry(other_source))
        everything = store.list_not_indexed()
        central = store.list_not_indexed("central")
        polled = store.list_not_indexed("central", IntakeKind.POLL)
    assert [e.key for e in everything] == sorted([KEY, other_ref, other_source])
    assert [e.key for e in central] == sorted([KEY, other_ref])
    assert [e.key for e in polled] == [KEY]


def test_delete_by_key(provider: PostgresStoreProvider) -> None:
    """Ensure deletes remove exactly the given keys."""
    other = dataclasses.replace(KEY, path="b.md")
    with provider.unit_of_work() as store:
        store.put_not_indexed(entry())
        store.put_not_indexed(entry(other))
        assert store.delete_not_indexed([]) == 0
        unknown = dataclasses.replace(KEY, ref="x")
        deleted = store.delete_not_indexed([KEY, unknown])
        remaining = store.list_not_indexed()
    assert deleted == 1
    assert [e.key for e in remaining] == [other]
