"""
Polling writes and clears the not-indexed list automatically.

Driven through the fake adapter. Entries are keyed by location and
ref; the duplicate-UUID reason is covered in ``test_poll_identity``.
"""

from pathlib import Path

import pytest

from app.domain.issues import IssueCode, error
from app.services.polling import PollingService
from app.storage.port import (
    IntakeKind,
    NotIndexedEntry,
    NotIndexedKey,
    NotIndexedWrite,
    PollStatus,
)
from app.storage.postgres.store import PostgresStoreProvider
from tests.fakes import FakeSource
from tests.services.test_polling import adr, make_config, service

A = "doc/decisions/2024-01-01-a.md"
B = "doc/decisions/2024-01-02-b.md"
NO_UUID = "---\ntitle: No identity\n---\nBody.\n"
BAD_YAML = "---\nuuid: [unclosed\n---\nBody.\n"


def entries(provider: PostgresStoreProvider) -> list[NotIndexedEntry]:
    """
    Read the whole not-indexed list.

    :param provider: Store provider.
    :returns: The entries, ordered by key.
    """
    with provider.unit_of_work() as store:
        return store.list_not_indexed()


def codes(provider: PostgresStoreProvider) -> dict[str, list[IssueCode]]:
    """
    Read the reason codes of every entry by path.

    :param provider: Store provider.
    :returns: Path -> reason codes.
    """
    return {e.key.path: [r.code for r in e.reasons] for e in entries(provider)}


@pytest.fixture
def world() -> FakeSource:
    """
    Build a source with one valid and one UUID-less file.

    :returns: The fake source.
    """
    source = FakeSource()
    source.put("platform", A, adr("A"), "t1")
    source.put("platform", B, NO_UUID, "t1")
    return source


@pytest.fixture
def polling(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> PollingService:
    """
    Build the polling service of registration ``one``.

    :param tmp_path: Temporary directory.
    :param provider: Store provider.
    :param world: The fake source.
    :returns: The service.
    """
    return service(provider, make_config(tmp_path, {"one": world}, ["one"]))


async def test_document_without_uuid_is_listed_not_indexed(
    polling: PollingService, provider: PostgresStoreProvider
) -> None:
    """Ensure a file without a UUID is queued with its reason and content."""
    (outcome,) = await polling.poll_all()

    [entry] = entries(provider)
    assert outcome.status is PollStatus.OK
    assert outcome.counts.not_indexed == 1
    assert entry.key == NotIndexedKey("one", "platform", B, "main")
    assert [r.code for r in entry.reasons] == [IssueCode.MISSING_UUID]
    assert entry.origin is IntakeKind.POLL
    assert entry.change_token == "t1"
    assert entry.source_url == f"fake://platform/{B}"
    with provider.unit_of_work() as store:
        assert entry.digest is not None
        revision = store.get_revision(entry.digest)
        assert len(store.list_change_tokens("one")) == 1
    assert revision is not None and "No identity" in revision.content


async def test_unparseable_frontmatter_is_listed_not_indexed(
    polling: PollingService, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure broken YAML is queued with ``bad_yaml``."""
    world.put("platform", B, BAD_YAML, "t1")

    await polling.poll_all()

    assert codes(provider) == {B: [IssueCode.BAD_YAML]}


async def test_unchanged_entry_is_not_read_again(
    polling: PollingService, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a queued file with an unchanged token is skipped."""
    await polling.poll_all()
    [before] = entries(provider)
    world.fetched.clear()

    (outcome,) = await polling.poll_all()

    assert world.fetched == []
    assert outcome.counts.unchanged == 2
    assert entries(provider) == [before]
    assert world.listed_tokens["platform"] == {A: "t1", B: "t1"}


async def test_fixed_document_is_indexed_and_cleared(
    polling: PollingService, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a fixed file is indexed and leaves the list."""
    await polling.poll_all()
    world.put("platform", B, adr("B"), "t2")

    (outcome,) = await polling.poll_all()

    assert entries(provider) == []
    assert outcome.counts.created == 1


async def test_reason_is_rewritten_keeping_first_seen(
    polling: PollingService, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a still-broken file updates its entry in place."""
    await polling.poll_all()
    [before] = entries(provider)
    world.put("platform", B, BAD_YAML, "t2")

    await polling.poll_all()

    [after] = entries(provider)
    assert [r.code for r in after.reasons] == [IssueCode.BAD_YAML]
    assert after.first_seen_at == before.first_seen_at
    assert after.change_token == "t2"


async def test_unreadable_document_is_listed_and_retried(
    polling: PollingService, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a failed fetch is queued, retried, and cleared once read."""
    world.put("platform", "doc/decisions/2024-01-03-c.md", adr("C"), "t1")
    world.fail_fetch.add("doc/decisions/2024-01-03-c.md")

    (failed,) = await polling.poll_all()
    unreadable = codes(provider)
    world.fail_fetch.clear()
    (retried,) = await polling.poll_all()

    assert failed.status is PollStatus.PARTIAL
    assert unreadable["doc/decisions/2024-01-03-c.md"] == [
        IssueCode.FETCH_FAILED
    ]
    assert retried.counts.created == 1
    assert codes(provider) == {B: [IssueCode.MISSING_UUID]}


async def test_removed_file_clears_its_entry_on_a_complete_listing(
    polling: PollingService, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure an entry clears only when a complete listing lacks it."""
    await polling.poll_all()
    del world.projects["platform"][B]
    world.incomplete_listing.add("platform")

    await polling.poll_all()
    kept = codes(provider)
    world.incomplete_listing.clear()
    await polling.poll_all()

    assert kept == {B: [IssueCode.MISSING_UUID]}
    assert entries(provider) == []


async def test_vanished_project_clears_its_entries(
    polling: PollingService, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a project gone from a complete listing loses its entries."""
    await polling.poll_all()
    world.put("payments", A, adr("Pay"), "t1")
    del world.projects["platform"]
    world.projects_complete = False

    await polling.poll_all()
    kept = codes(provider)
    world.projects_complete = True
    await polling.poll_all()

    assert kept == {B: [IssueCode.MISSING_UUID]}
    assert entries(provider) == []


async def test_removed_registration_clears_its_entries(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a registration dropped from the config loses its entries."""
    await service(
        provider, make_config(tmp_path, {"one": world}, ["one"])
    ).poll_all()
    other = FakeSource()
    other.put("platform", A, adr("Other"), "t1")
    config = make_config(tmp_path, {"two": other}, ["two"])

    await service(provider, config).poll_all()

    assert entries(provider) == []


async def test_removed_registration_clears_its_push_entries(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a registration dropped from the config loses push entries."""
    await service(
        provider, make_config(tmp_path, {"one": world}, ["one"])
    ).poll_all()
    pushed = NotIndexedWrite(
        key=NotIndexedKey("one", "platform", "doc/decisions/x.md", "feature"),
        origin=IntakeKind.PUSH,
        reasons=(error(IssueCode.BAD_UUID, "bad"),),
    )
    with provider.unit_of_work() as store:
        store.put_not_indexed(pushed)
    other = FakeSource()
    config = make_config(tmp_path, {"two": other}, ["two"])

    await service(provider, config).poll_all()

    assert entries(provider) == []


async def test_poll_never_clears_push_entries(
    polling: PollingService, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure poll reconciliation leaves push-origin entries alone."""
    pushed = NotIndexedWrite(
        key=NotIndexedKey("one", "platform", "doc/decisions/x.md", "feature"),
        origin=IntakeKind.PUSH,
        reasons=(error(IssueCode.BAD_UUID, "bad"),),
    )
    with provider.unit_of_work() as store:
        store.put_not_indexed(pushed)
    del world.projects["platform"][B]

    await polling.poll_all()

    assert [(e.key, e.origin) for e in entries(provider)] == [
        (pushed.key, IntakeKind.PUSH)
    ]


async def test_entry_at_an_old_ref_is_replaced(
    polling: PollingService, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a renamed published ref does not leave a stale entry."""
    await polling.poll_all()
    world.ref = "trunk"
    world.put("platform", B, BAD_YAML, "t2")

    await polling.poll_all()

    assert [e.key.ref for e in entries(provider)] == ["trunk"]


async def test_not_indexed_document_releases_the_uuid_it_held(
    polling: PollingService, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a holder whose UUID breaks is removed and queued."""
    await polling.poll_all()
    with provider.unit_of_work() as store:
        [held] = store.list_change_tokens("one")
    world.put("platform", A, NO_UUID.replace("No identity", "Broken"), "t2")

    (outcome,) = await polling.poll_all()

    with provider.unit_of_work() as store:
        assert store.get_published(held.adr_uuid) is None
    assert outcome.counts.deleted == 1
    assert set(codes(provider)) == {A, B}
