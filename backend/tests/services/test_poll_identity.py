"""
Polling keys ADRs by UUID: moves, the holder rule and deletion.

Driven through the fake adapter; every registration of a test polls
its own :class:`~tests.fakes.FakeSource`.
"""

import uuid
from pathlib import Path

from app.domain.approval import DecisionAction
from app.domain.issues import IssueCode
from app.services.polling import PollingService
from app.storage.port import IntakeKind, NewDecision, PollStatus, StoredRecord
from app.storage.postgres.store import PostgresStoreProvider
from tests.fakes import FakeSource
from tests.services.test_polling import adr, make_config, service

X = uuid.UUID("5e1f0000-0000-4000-8000-000000000001")
A = "doc/decisions/2024-01-01-a.md"
B = "doc/decisions/2024-01-02-b.md"
EARLY = "doc/decisions/2023-12-31-early.md"


def published(provider: PostgresStoreProvider) -> StoredRecord:
    """
    Read the published row of :data:`X`.

    :param provider: Store provider.
    :returns: The row.
    """
    with provider.unit_of_work() as store:
        row = store.get_published(X)
    assert row is not None
    return row


def build(
    tmp_path: Path,
    provider: PostgresStoreProvider,
    worlds: dict[str, FakeSource],
) -> PollingService:
    """
    Configure one fake registration per world, in dict order.

    :param tmp_path: Temporary directory.
    :param provider: Store provider.
    :param worlds: Fake sources by registration id.
    :returns: The polling service.
    """
    config = make_config(tmp_path, worlds, list(worlds))
    return service(provider, config)


def accept(provider: PostgresStoreProvider, digest: str) -> None:
    """
    Accept a digest of :data:`X`.

    :param provider: Store provider.
    :param digest: The decided digest.
    """
    with provider.unit_of_work() as store:
        store.append_decision(
            NewDecision(
                adr_uuid=X,
                digest=digest,
                action=DecisionAction.ACCEPTED,
                actor_issuer="iss",
                actor_subject="sub",
                actor_display=None,
                actor_email=None,
                comment=None,
                policy_id="global",
                policy_version=1,
            )
        )


def queued(provider: PostgresStoreProvider) -> dict[tuple[str, str], object]:
    """
    Read the not-indexed list as ``(source, path) -> holder UUID``.

    :param provider: Store provider.
    :returns: The entries.
    """
    with provider.unit_of_work() as store:
        entries = store.list_not_indexed()
    return {(e.key.source_id, e.key.path): e.holder_uuid for e in entries}


async def test_renamed_file_keeps_its_identity(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure a path change is a move: same row, history and approvals."""
    world = FakeSource()
    world.put("platform", A, adr("A", X), "t1")
    polling = build(tmp_path, provider, {"one": world})
    await polling.poll_all()
    before = published(provider)
    accept(provider, before.digest)
    del world.projects["platform"][A]
    world.put("platform", B, adr("A", X), "t1")

    (outcome,) = await polling.poll_all()

    after = published(provider)
    assert (outcome.counts.moved, outcome.counts.deleted) == (1, 0)
    assert after.path == B
    assert after.first_seen_at == before.first_seen_at
    assert after.digest == before.digest
    with provider.unit_of_work() as store:
        assert [e.digest for e in store.list_decisions(X)] == [before.digest]


async def test_move_across_projects_keeps_identity(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure a file moved to another project keeps its row."""
    world = FakeSource()
    world.put("platform", A, adr("A", X), "t1")
    polling = build(tmp_path, provider, {"one": world})
    await polling.poll_all()
    first_seen = published(provider).first_seen_at
    del world.projects["platform"]
    world.put("payments", A, adr("A", X), "t1")

    (outcome,) = await polling.poll_all()

    row = published(provider)
    assert (row.project, row.first_seen_at) == ("payments", first_seen)
    assert outcome.counts.moved == 1 and outcome.counts.deleted == 0


async def test_move_to_a_later_registration_keeps_identity(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure a move between registrations in one run is not a delete."""
    one, two = FakeSource(), FakeSource()
    one.put("platform", A, adr("A", X), "t1")
    polling = build(tmp_path, provider, {"one": one, "two": two})
    await polling.poll_all()
    first_seen = published(provider).first_seen_at
    del one.projects["platform"][A]
    two.put("platform", A, adr("A", X), "t1")

    first, second = await polling.poll_all()

    row = published(provider)
    assert (row.source_id, row.first_seen_at) == ("two", first_seen)
    assert first.counts.deleted == 0
    assert second.counts.moved == 1


async def test_move_to_an_earlier_registration_keeps_identity(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure a move into an earlier registration is a move too."""
    one, two = FakeSource(), FakeSource()
    two.put("platform", A, adr("A", X), "t1")
    polling = build(tmp_path, provider, {"one": one, "two": two})
    await polling.poll_all()
    first_seen = published(provider).first_seen_at
    del two.projects["platform"][A]
    one.put("platform", A, adr("A", X), "t1")

    first, second = await polling.poll_all()

    row = published(provider)
    assert (row.source_id, row.first_seen_at) == ("one", first_seen)
    assert first.counts.moved == 1
    assert second.counts.deleted == 0


async def test_existing_holder_wins_over_a_new_file(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure a later file with a held UUID is queued, even sorted first."""
    world = FakeSource()
    world.put("platform", A, adr("A", X), "t1")
    polling = build(tmp_path, provider, {"one": world})
    await polling.poll_all()
    world.put("platform", EARLY, adr("Copy", X), "t1")

    (outcome,) = await polling.poll_all()

    assert published(provider).path == A
    assert queued(provider) == {("one", EARLY): X}
    assert outcome.counts.not_indexed == 1
    assert outcome.status is PollStatus.OK


async def test_first_registration_wins_a_new_uuid_in_one_run(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure config order breaks a tie between two new files."""
    one, two = FakeSource(), FakeSource()
    one.put("platform", B, adr("One", X), "t1")
    two.put("apps", A, adr("Two", X), "t1")
    polling = build(tmp_path, provider, {"one": one, "two": two})

    await polling.poll_all()

    assert published(provider).source_id == "one"
    assert queued(provider) == {("two", A): X}


async def test_project_then_path_break_a_tie_in_one_registration(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure project order, then path order, picks the holder."""
    world = FakeSource()
    world.put("platform", A, adr("Platform", X), "t1")
    world.put("apps", B, adr("Apps B", X), "t1")
    world.put("apps", EARLY, adr("Apps early", X), "t1")
    polling = build(tmp_path, provider, {"one": world})

    await polling.poll_all()

    row = published(provider)
    assert (row.project, row.path) == ("apps", EARLY)
    assert queued(provider) == {("one", B): X, ("one", A): X}


async def test_duplicate_takes_over_when_the_holder_is_removed(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure a removed holder releases its UUID to the queued file."""
    world = FakeSource()
    world.put("platform", A, adr("A", X), "t1")
    polling = build(tmp_path, provider, {"one": world})
    await polling.poll_all()
    first_seen = published(provider).first_seen_at
    world.put("platform", B, adr("Copy", X), "t1")
    await polling.poll_all()
    del world.projects["platform"][A]

    (outcome,) = await polling.poll_all()

    row = published(provider)
    assert (row.path, row.title) == (B, "Copy")
    assert row.first_seen_at == first_seen
    assert queued(provider) == {}
    assert outcome.counts.moved == 1


async def test_holder_releases_its_uuid_by_changing_it(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure a holder that gets another UUID frees the old one."""
    world = FakeSource()
    world.put("platform", A, adr("A", X), "t1")
    world.put("platform", B, adr("Copy", X), "t1")
    polling = build(tmp_path, provider, {"one": world})
    await polling.poll_all()
    other = uuid.uuid4()
    world.put("platform", A, adr("A", other), "t2")

    await polling.poll_all()

    assert published(provider).path == B
    with provider.unit_of_work() as store:
        held = store.get_published(other)
    assert held is not None and held.path == A
    assert queued(provider) == {}


async def test_incomplete_listing_keeps_the_holder(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure a holder missing from an incomplete listing keeps its UUID."""
    world = FakeSource()
    world.put("platform", A, adr("A", X), "t1")
    polling = build(tmp_path, provider, {"one": world})
    await polling.poll_all()
    del world.projects["platform"][A]
    world.put("platform", B, adr("Copy", X), "t1")
    world.incomplete_listing.add("platform")

    (outcome,) = await polling.poll_all()

    assert outcome.status is PollStatus.PARTIAL
    assert published(provider).path == A
    assert queued(provider) == {("one", B): X}


async def test_holder_of_an_unpolled_registration_keeps_its_uuid(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure polling one registration cannot steal another's UUID."""
    one, two = FakeSource(), FakeSource()
    one.put("platform", A, adr("A", X), "t1")
    polling = build(tmp_path, provider, {"one": one, "two": two})
    await polling.poll_all()
    del one.projects["platform"][A]
    two.put("platform", A, adr("A", X), "t1")

    await polling.poll_source("two")

    assert published(provider).source_id == "one"
    assert queued(provider) == {("two", A): X}


async def test_holder_of_a_removed_registration_releases(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure a registration removed from the config holds nothing."""
    gone, kept = FakeSource(), FakeSource()
    gone.put("platform", A, adr("A", X), "t1")
    await build(tmp_path, provider, {"gone": gone}).poll_all()
    first_seen = published(provider).first_seen_at
    kept.put("platform", B, adr("A", X), "t1")

    (outcome,) = await build(tmp_path, provider, {"kept": kept}).poll_all()

    row = published(provider)
    assert (row.source_id, row.path) == ("kept", B)
    assert row.first_seen_at == first_seen
    assert outcome.counts.moved == 1


async def test_complete_listing_deletes_and_frees_the_uuid(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure a removed file's row is deleted; its approvals stay."""
    world = FakeSource()
    world.put("platform", A, adr("A", X), "t1")
    polling = build(tmp_path, provider, {"one": world})
    await polling.poll_all()
    accept(provider, published(provider).digest)
    del world.projects["platform"][A]

    (outcome,) = await polling.poll_all()

    assert outcome.counts.deleted == 1
    with provider.unit_of_work() as store:
        assert store.get_published(X) is None
        assert len(store.list_decisions(X)) == 1


async def test_duplicate_reason_names_the_holder(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure the queued duplicate explains where the UUID is held."""
    world = FakeSource()
    world.put("platform", A, adr("A", X), "t1")
    world.put("platform", B, adr("Copy", X), "t1")

    await build(tmp_path, provider, {"one": world}).poll_all()

    with provider.unit_of_work() as store:
        [entry] = store.list_not_indexed()
    [reason] = entry.reasons
    assert reason.code is IssueCode.DUPLICATE_UUID
    assert f"one/platform/{A}" in reason.message
    assert entry.origin is IntakeKind.POLL
    assert entry.change_token is None
    assert entry.digest is not None
