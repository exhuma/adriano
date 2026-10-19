"""Tests for poll orchestration (driven through the fake adapter)."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from app.catalog_config import CatalogConfig, load_catalog_config
from app.errors import NotFoundError
from app.services.polling import PollingService, PollOutcome
from app.services.registrations import sync_registrations
from app.sources.registry import default_registry
from app.storage.port import ChangeTokenEntry, PollStatus
from app.storage.postgres.store import PostgresStoreProvider
from tests.fakes import FakeSource, FakeSourceType

A = "doc/decisions/2024-01-01-a.md"
B = "doc/decisions/sub/2024-01-02-b.md"


def adr(title: str) -> str:
    """
    Build a valid ADR document with a fresh UUID.

    :param title: Title.
    :returns: The text.
    """
    return f"---\nuuid: {uuid.uuid4()}\ntitle: {title}\n---\nBody.\n"


def make_config(
    tmp_path: Path, worlds: dict[str, FakeSource], ids: list[str]
) -> CatalogConfig:
    """
    Load a configuration with one fake registration per id.

    Each registration ``<id>`` is bound to ``worlds[<id>]``.

    :param tmp_path: Temporary directory.
    :param worlds: Fake sources by registration id.
    :param ids: Registration ids in configuration order.
    :returns: The configuration.
    """
    entries = "".join(
        f"  - {{id: {i}, type: fake, world: {i}, published_ref: main}}\n"
        for i in ids
    )
    path = tmp_path / "catalog.yaml"
    path.write_text(f"sources:\n{entries}", encoding="utf-8")
    registry = default_registry()
    registry.register("fake", FakeSourceType(worlds))
    return load_catalog_config(path, env={}, registry=registry)


@pytest.fixture
def world() -> FakeSource:
    """
    Build a fake source with two projects.

    :returns: The fake source.
    """
    source = FakeSource()
    source.put("platform", A, adr("A"), "t1")
    source.put("platform", B, adr("B"), "t1")
    source.put("platform", "doc/decisions/README.md", "# not an ADR", "t1")
    source.put("payments", A, adr("Pay"), "t1")
    return source


def service(
    provider: PostgresStoreProvider, config: CatalogConfig
) -> PollingService:
    """
    Sync registrations and build the service.

    :param provider: Store provider.
    :param config: Configuration.
    :returns: The service.
    """
    sync_registrations(provider, config)
    return PollingService(provider, config.sources, concurrency=2)


def tokens(
    provider: PostgresStoreProvider, source_id: str = "one"
) -> dict[tuple[str, str], ChangeTokenEntry]:
    """
    Read stored published rows of a registration.

    :param provider: Store provider.
    :param source_id: Registration id.
    :returns: Entries by ``(project, path)``.
    """
    with provider.unit_of_work() as store:
        entries = store.list_change_tokens(source_id)
    return {(e.project, e.path): e for e in entries}


def run_row(engine: Engine, outcome: PollOutcome) -> dict[str, object]:
    """
    Read the intake run of an outcome.

    :param engine: Engine.
    :param outcome: Poll outcome.
    :returns: The row as a mapping.
    """
    with engine.connect() as connection:
        row = (
            connection.execute(
                text("SELECT * FROM intake_run WHERE id = :id"),
                {"id": outcome.run_id},
            )
            .mappings()
            .one()
        )
    return dict(row)


async def test_first_poll_ingests_and_logs_the_run(
    tmp_path: Path,
    provider: PostgresStoreProvider,
    engine: Engine,
    world: FakeSource,
) -> None:
    """Ensure a first poll stores all ADRs and records an ok run."""
    config = make_config(tmp_path, {"one": world}, ["one"])

    outcome = await service(provider, config).poll_source("one")

    assert outcome.status is PollStatus.OK
    assert set(tokens(provider)) == {
        ("platform", A),
        ("platform", B),
        ("payments", A),
    }
    assert outcome.counts.created == 3
    assert sorted(world.fetched) == sorted(
        ["platform/" + A, "platform/" + B, "payments/" + A]
    )
    row = run_row(engine, outcome)
    assert row["status"] == "ok" and row["kind"] == "poll"
    assert row["finished_at"] is not None
    with provider.unit_of_work() as store:
        registration = store.get_registration("one")
    assert registration is not None
    assert registration.last_status is PollStatus.OK
    assert registration.last_success_at is not None


async def test_unchanged_tokens_are_not_fetched(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a second poll passes stored tokens and fetches nothing."""
    polling = service(provider, make_config(tmp_path, {"one": world}, ["one"]))
    await polling.poll_all()
    world.fetched.clear()

    outcome = await polling.poll_all()

    assert world.fetched == []
    assert outcome[0].counts.unchanged == 3
    assert world.listed_tokens["platform"] == {A: "t1", B: "t1"}


async def test_changed_content_is_refetched_and_updated(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a moved token refetches and records the new digest."""
    polling = service(provider, make_config(tmp_path, {"one": world}, ["one"]))
    await polling.poll_all()
    before = tokens(provider)[("platform", A)]
    world.put("platform", A, adr("A2"), "t2")
    world.fetched.clear()

    (outcome,) = await polling.poll_all()

    assert world.fetched == ["platform/" + A]
    assert outcome.counts.updated == 1
    after = tokens(provider)[("platform", A)]
    assert after.digest != before.digest and after.change_token == "t2"


async def test_unchanged_document_with_new_token_is_refreshed(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure changed=False with a new token only rewrites the token."""
    polling = service(provider, make_config(tmp_path, {"one": world}, ["one"]))
    await polling.poll_all()
    before = tokens(provider)[("platform", A)]
    world.unchanged_override[A] = "head2:t1"
    world.fetched.clear()

    (outcome,) = await polling.poll_all()

    assert world.fetched == []
    assert outcome.counts.tokens_refreshed == 2  # A in both projects
    after = tokens(provider)[("platform", A)]
    assert after.change_token == "head2:t1"
    assert after.digest == before.digest and after.id == before.id


async def test_complete_poll_deletes_removed_files_and_projects(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure a complete poll reconciles deleted files and projects."""
    polling = service(provider, make_config(tmp_path, {"one": world}, ["one"]))
    await polling.poll_all()
    del world.projects["platform"][B]
    del world.projects["payments"]

    (outcome,) = await polling.poll_all()

    assert outcome.status is PollStatus.OK
    assert outcome.counts.deleted == 2
    assert set(tokens(provider)) == {("platform", A)}


async def test_incomplete_listings_delete_nothing(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure incomplete document or project listings preserve rows."""
    polling = service(provider, make_config(tmp_path, {"one": world}, ["one"]))
    await polling.poll_all()
    del world.projects["platform"][B]
    world.incomplete_listing.add("platform")

    (partial,) = await polling.poll_all()

    assert partial.status is PollStatus.PARTIAL
    assert ("platform", B) in tokens(provider)
    world.incomplete_listing.clear()
    world.projects_complete = False
    del world.projects["payments"]

    (projects_partial,) = await polling.poll_all()

    assert projects_partial.status is PollStatus.PARTIAL
    assert projects_partial.counts.deleted == 0
    assert set(tokens(provider)) == {
        ("platform", A),
        ("platform", B),
        ("payments", A),
    }


async def test_failed_poll_preserves_content_and_reports(
    tmp_path: Path,
    provider: PostgresStoreProvider,
    engine: Engine,
    world: FakeSource,
) -> None:
    """Ensure a source failure keeps prior rows and records the failure."""
    polling = service(provider, make_config(tmp_path, {"one": world}, ["one"]))
    await polling.poll_all()
    with provider.unit_of_work() as store:
        ok = store.get_registration("one")
    world.fail_projects = True

    (outcome,) = await polling.poll_all()

    assert outcome.status is PollStatus.FAILED
    assert [p.code for p in outcome.problems] == ["source_error"]
    assert len(tokens(provider)) == 3
    assert run_row(engine, outcome)["status"] == "failed"
    with provider.unit_of_work() as store:
        registration = store.get_registration("one")
    assert registration is not None and ok is not None
    assert registration.last_status is PollStatus.FAILED
    assert registration.last_success_at == ok.last_success_at
    assert registration.last_error == {
        "problems": [{"code": "source_error", "message": "fake source is down"}]
    }


async def test_listing_and_fetch_failures_are_partial(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure per-project and per-file failures keep their old rows."""
    polling = service(provider, make_config(tmp_path, {"one": world}, ["one"]))
    await polling.poll_all()
    before = tokens(provider)
    world.put("platform", A, adr("A2"), "t2")
    world.fail_fetch.add(A)
    world.fail_listing.add("payments")

    (outcome,) = await polling.poll_all()

    assert outcome.status is PollStatus.PARTIAL
    assert {p.code for p in outcome.problems} == {
        "fetch_failed",
        "listing_failed",
    }
    assert tokens(provider) == before


async def test_one_failing_registration_does_not_affect_others(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure poll_all continues after a failed registration."""
    broken = FakeSource(fail_projects=True)
    config = make_config(
        tmp_path, {"one": broken, "two": world}, ["one", "two"]
    )

    outcomes = await service(provider, config).poll_all()

    assert [o.status for o in outcomes] == [PollStatus.FAILED, PollStatus.OK]
    assert len(tokens(provider, "two")) == 3


async def test_first_registration_in_config_order_owns_a_location(
    tmp_path: Path, provider: PostgresStoreProvider, world: FakeSource
) -> None:
    """Ensure overlapping registrations do not duplicate records."""
    overlap = FakeSource()
    overlap.put("platform", A, adr("Other A"), "x1")
    overlap.put("other", A, adr("Unique"), "x1")
    config = make_config(
        tmp_path, {"one": world, "two": overlap}, ["one", "two"]
    )

    first, second = await service(provider, config).poll_all()

    assert first.status is PollStatus.OK and second.status is PollStatus.OK
    assert set(tokens(provider, "two")) == {("other", A)}
    assert second.counts.skipped_owned == 1
    conflict = [p for p in second.problems if p.code == "ownership_conflict"]
    assert [(p.project, p.path) for p in conflict] == [("platform", A)]


async def test_poll_source_rejects_unknown_and_disabled_sources(
    tmp_path: Path, provider: PostgresStoreProvider
) -> None:
    """Ensure unknown ids raise and invalid registrations do not run."""
    config = make_config(tmp_path, {}, ["ghost"])
    polling = service(provider, config)

    with pytest.raises(NotFoundError):
        await polling.poll_source("nope")
    outcome = await polling.poll_source("ghost")

    assert outcome.status is PollStatus.DISABLED
    assert outcome.run_id is None
    assert "unknown world" in outcome.problems[0].message
    assert await polling.poll_all() == []
