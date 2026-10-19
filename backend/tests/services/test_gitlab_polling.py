"""End-to-end polling tests for the GitLab adapter (real Postgres)."""

import functools
import logging
import uuid
from pathlib import Path

import pytest

from app.catalog_config import CatalogConfig, load_catalog_config
from app.services.polling import PollingService
from app.services.registrations import sync_registrations
from app.sources import gitlab
from app.sources.registry import SourceTypeRegistry, default_registry
from app.storage.port import ChangeTokenEntry, PollStatus
from app.storage.postgres.store import PostgresStoreProvider
from tests.gitlab_fake import BASE_URL, TOKEN, FakeGitLab, FakeRepo

A = "doc/decisions/2024-01-01-a.md"
B = "doc/decisions/sub/2024-01-02-b.md"
C = "doc/decisions/2024-02-02-c.md"


def adr(title: str) -> str:
    """
    Build a valid ADR document with a fresh UUID.

    :param title: Title.
    :returns: The text.
    """
    return f"---\nuuid: {uuid.uuid4()}\ntitle: {title}\n---\nBody.\n"


async def no_sleep(_seconds: float) -> None:
    """
    Skip retry waits.

    :param _seconds: Requested wait.
    """


def registry(fake: FakeGitLab) -> SourceTypeRegistry:
    """
    Build a registry whose gitlab type talks to the fake.

    :param fake: Fake GitLab.
    :returns: The registry.
    """
    result = default_registry()
    result.register(
        "gitlab",
        functools.partial(
            gitlab.validate_settings,
            transport=fake.transport(),
            sleep=no_sleep,
        ),
    )
    return result


def make_config(tmp_path: Path, fake: FakeGitLab) -> CatalogConfig:
    """
    Load a one-registration ``gitlab`` configuration.

    :param tmp_path: Directory to write ``catalog.yaml`` into.
    :param fake: Fake GitLab.
    :returns: The configuration.
    """
    path = tmp_path / "catalog.yaml"
    path.write_text(
        "sources:\n"
        "  - id: gl\n"
        "    type: gitlab\n"
        f"    base_url: {BASE_URL}\n"
        "    token_env: GL_TOKEN\n"
        "    scope: {groups: [platform], include_subgroups: true}\n"
        "    published_ref: '@project-default'\n",
        encoding="utf-8",
    )
    return load_catalog_config(
        path, env={"GL_TOKEN": TOKEN}, registry=registry(fake)
    )


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
    provider: PostgresStoreProvider,
) -> dict[tuple[str, str], ChangeTokenEntry]:
    """
    Read stored published rows of the registration.

    :param provider: Store provider.
    :returns: Entries by ``(project, path)``.
    """
    with provider.unit_of_work() as store:
        entries = store.list_change_tokens("gl")
    return {(e.project, e.path): e for e in entries}


@pytest.fixture
def fake() -> FakeGitLab:
    """
    Build a fake with two projects (one in a subgroup) and three ADRs.

    :returns: The fake.
    """
    instance = FakeGitLab(page_size=2)
    api = instance.repo("platform/api")
    api.put(A, adr("A"))
    api.put(B, adr("B"))
    api.put("doc/decisions/README.md", "# not an ADR")
    instance.repo("platform/team/pay").put(C, adr("C"))
    instance.groups.add("platform")
    return instance


def repo(fake: FakeGitLab, path: str) -> FakeRepo:
    """
    Look up a fake repo.

    :param fake: Fake GitLab.
    :param path: Project path.
    :returns: The repo.
    """
    return fake.repos[path]


async def test_polls_ingest_then_skip_unchanged_branches(
    tmp_path: Path, provider: PostgresStoreProvider, fake: FakeGitLab
) -> None:
    """Ensure a second poll of unchanged branches lists no tree."""
    polling = service(provider, make_config(tmp_path, fake))

    first = await polling.poll_source("gl")
    trees, blobs = fake.calls("tree"), fake.calls("blob")
    second = await polling.poll_source("gl")

    assert first.status is PollStatus.OK
    assert first.counts.created == 3
    assert set(tokens(provider)) == {
        ("platform/api", A),
        ("platform/api", B),
        ("platform/team/pay", C),
    }
    assert second.status is PollStatus.OK
    assert second.counts.unchanged == 3
    assert (fake.calls("tree"), fake.calls("blob")) == (trees, blobs)


async def test_moved_head_fetches_only_changed_blobs(
    tmp_path: Path, provider: PostgresStoreProvider, fake: FakeGitLab
) -> None:
    """Ensure a new commit refetches only the file whose blob changed."""
    polling = service(provider, make_config(tmp_path, fake))
    await polling.poll_source("gl")
    blobs = fake.calls("blob")
    repo(fake, "platform/api").put(B, adr("B2"))

    outcome = await polling.poll_source("gl")

    assert outcome.status is PollStatus.OK
    assert outcome.counts.updated == 1
    assert outcome.counts.tokens_refreshed == 1
    assert fake.calls("blob") == blobs + 1
    head = repo(fake, "platform/api").head
    assert head in (tokens(provider)[("platform/api", A)].change_token or "")


async def test_failed_new_file_is_retried_on_an_unchanged_head(
    tmp_path: Path, provider: PostgresStoreProvider, fake: FakeGitLab
) -> None:
    """Ensure a new file whose fetch failed is fetched by the next poll."""
    polling = service(provider, make_config(tmp_path, fake))
    await polling.poll_source("gl")
    new = "doc/decisions/2024-03-03-new.md"
    repo(fake, "platform/api").put(new, adr("New"))
    fake.down.add("blob")

    failed = await polling.poll_source("gl")
    missing = ("platform/api", new) not in tokens(provider)
    fake.down.clear()
    retried = await polling.poll_source("gl")

    assert failed.status is PollStatus.PARTIAL
    assert missing
    assert retried.status is PollStatus.OK
    assert retried.counts.created == 1
    assert ("platform/api", new) in tokens(provider)


async def test_persistent_failure_is_partial_and_deletes_nothing(
    tmp_path: Path, provider: PostgresStoreProvider, fake: FakeGitLab
) -> None:
    """Ensure a project that keeps failing keeps all of its records."""
    polling = service(provider, make_config(tmp_path, fake))
    await polling.poll_source("gl")
    before = tokens(provider)
    repo(fake, "platform/api").remove(B)
    fake.down.add("tree")

    outcome = await polling.poll_source("gl")

    assert outcome.status is PollStatus.PARTIAL
    assert outcome.counts.deleted == 0
    assert "listing_failed" in {p.code for p in outcome.problems}
    assert tokens(provider) == before


async def test_failed_group_listing_deletes_nothing(
    tmp_path: Path, provider: PostgresStoreProvider, fake: FakeGitLab
) -> None:
    """Ensure an unreadable group listing preserves every record."""
    polling = service(provider, make_config(tmp_path, fake))
    await polling.poll_source("gl")
    before = tokens(provider)
    fake.down.add("groups")

    outcome = await polling.poll_source("gl")

    assert outcome.status is PollStatus.PARTIAL
    assert tokens(provider) == before


async def test_archived_project_is_removed_on_a_complete_listing(
    tmp_path: Path, provider: PostgresStoreProvider, fake: FakeGitLab
) -> None:
    """Ensure archiving a project removes its records, and deletions."""
    polling = service(provider, make_config(tmp_path, fake))
    await polling.poll_source("gl")
    repo(fake, "platform/team/pay").archived = True
    repo(fake, "platform/api").remove(B)

    outcome = await polling.poll_source("gl")

    assert outcome.status is PollStatus.OK
    assert outcome.counts.deleted == 2
    assert set(tokens(provider)) == {("platform/api", A)}


async def test_out_of_scope_projects_are_ignored(
    tmp_path: Path, provider: PostgresStoreProvider, fake: FakeGitLab
) -> None:
    """Ensure projects outside the scoped groups are never polled."""
    stray = fake.repo("elsewhere/shared")
    stray.put(A, adr("Stray"))
    fake.stray.append(stray)

    outcome = await service(provider, make_config(tmp_path, fake)).poll_source(
        "gl"
    )

    assert outcome.status is PollStatus.OK
    assert all(project != "elsewhere/shared" for project, _ in tokens(provider))
    assert not any(f"projects/{stray.id}/" in str(r.url) for r in fake.requests)


async def test_token_never_appears_in_logs_or_problems(
    tmp_path: Path,
    provider: PostgresStoreProvider,
    fake: FakeGitLab,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure retries, failures and stored errors never expose the token."""
    caplog.set_level(logging.DEBUG)
    polling = service(provider, make_config(tmp_path, fake))
    fake.script["groups"] = [429, 500]
    fake.down.add("blob")

    outcome = await polling.poll_source("gl")

    assert outcome.status is PollStatus.PARTIAL
    assert caplog.text
    assert TOKEN not in caplog.text
    assert TOKEN not in repr(outcome)
    with provider.unit_of_work() as store:
        row = store.get_registration("gl")
    assert row is not None
    assert TOKEN not in repr(row)
