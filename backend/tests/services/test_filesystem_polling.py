"""End-to-end polling tests for the filesystem adapter (real Postgres)."""

import os
import shutil
import uuid
from pathlib import Path

import pytest

from app.catalog_config import CatalogConfig, load_catalog_config
from app.services.polling import PollingService
from app.services.registrations import sync_registrations
from app.sources import filesystem
from app.sources.port import FetchedDocument, SourceDocument
from app.sources.registry import default_registry
from app.storage.port import ChangeTokenEntry, PollStatus
from app.storage.postgres.store import PostgresStoreProvider

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


def write(path: Path, text: str) -> None:
    """
    Write a file, creating parent directories as needed.

    :param path: File path.
    :param text: Content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_config(
    tmp_path: Path, root: Path, *, projects: list[str] | None = None
) -> CatalogConfig:
    """
    Load a one-registration ``filesystem`` configuration.

    :param tmp_path: Directory to write ``catalog.yaml`` into.
    :param root: Filesystem adapter root.
    :param projects: Optional ``scope.projects`` filter.
    :returns: The configuration.
    """
    scope = f"\n    scope: {{projects: {projects}}}" if projects else ""
    path = tmp_path / "catalog.yaml"
    path.write_text(
        "sources:\n"
        "  - id: fs\n"
        "    type: filesystem\n"
        f"    root: {root}\n"
        f"    published_ref: local{scope}\n",
        encoding="utf-8",
    )
    return load_catalog_config(path, env={}, registry=default_registry())


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
    provider: PostgresStoreProvider, source_id: str = "fs"
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


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """
    Build a two-project ADR tree with a nested file and a non-ADR file.

    :param tmp_path: Temporary directory.
    :returns: The root directory.
    """
    root = tmp_path / "root"
    write(root / "platform" / A, adr("A"))
    write(root / "platform" / B, adr("B"))
    write(root / "platform/doc/decisions/README.md", "# not an ADR")
    write(root / "payments" / C, adr("C"))
    return root


async def test_first_poll_ingests_recursively_and_ignores_non_adr(
    tmp_path: Path, provider: PostgresStoreProvider, tree: Path
) -> None:
    """Ensure a first poll discovers nested ADRs and skips other files."""
    config = make_config(tmp_path, tree)

    outcome = await service(provider, config).poll_source("fs")

    assert outcome.status is PollStatus.OK
    assert set(tokens(provider)) == {
        ("platform", A),
        ("platform", B),
        ("payments", C),
    }
    assert outcome.counts.created == 3


async def test_second_poll_does_not_read_unchanged_files(
    tmp_path: Path,
    provider: PostgresStoreProvider,
    tree: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure unchanged files are listed again but never re-fetched."""
    config = make_config(tmp_path, tree)
    polling = service(provider, config)
    await polling.poll_source("fs")
    calls: list[str] = []
    original = filesystem.FilesystemAdapter.fetch

    async def spy(
        self: filesystem.FilesystemAdapter, document: SourceDocument
    ) -> FetchedDocument:
        calls.append(document.path)
        return await original(self, document)

    monkeypatch.setattr(filesystem.FilesystemAdapter, "fetch", spy)

    outcome = await polling.poll_source("fs")

    assert calls == []
    assert outcome.counts.unchanged == 3


async def test_changed_file_is_refetched_and_updated(
    tmp_path: Path, provider: PostgresStoreProvider, tree: Path
) -> None:
    """Ensure a modified file is refetched and its digest updated."""
    config = make_config(tmp_path, tree)
    polling = service(provider, config)
    await polling.poll_source("fs")
    before = tokens(provider)[("platform", A)]
    target = tree / "platform" / A
    new_mtime = target.stat().st_mtime + 10
    write(target, adr("A2"))
    os.utime(target, (new_mtime, new_mtime))

    outcome = await polling.poll_source("fs")

    assert outcome.counts.updated == 1
    after = tokens(provider)[("platform", A)]
    assert after.digest != before.digest


async def test_complete_poll_deletes_removed_files_and_projects(
    tmp_path: Path, provider: PostgresStoreProvider, tree: Path
) -> None:
    """Ensure a complete walk reconciles deletions, including a project."""
    config = make_config(tmp_path, tree)
    polling = service(provider, config)
    await polling.poll_source("fs")
    (tree / "platform" / B).unlink()
    shutil.rmtree(tree / "payments")

    outcome = await polling.poll_source("fs")

    assert outcome.status is PollStatus.OK
    assert outcome.counts.deleted == 2
    assert set(tokens(provider)) == {("platform", A)}


async def test_missing_root_fails_the_poll_and_keeps_records(
    tmp_path: Path, provider: PostgresStoreProvider, tree: Path
) -> None:
    """Ensure a vanished root fails the poll without deleting anything."""
    config = make_config(tmp_path, tree)
    polling = service(provider, config)
    await polling.poll_source("fs")
    before = tokens(provider)
    shutil.rmtree(tree)

    outcome = await polling.poll_source("fs")

    assert outcome.status is PollStatus.FAILED
    assert [p.code for p in outcome.problems] == ["source_error"]
    assert tokens(provider) == before


async def test_scope_filters_projects(
    tmp_path: Path, provider: PostgresStoreProvider, tree: Path
) -> None:
    """Ensure ``scope.projects`` restricts polling to the named projects."""
    config = make_config(tmp_path, tree, projects=["platform"])

    outcome = await service(provider, config).poll_source("fs")

    assert outcome.status is PollStatus.OK
    assert set(tokens(provider)) == {("platform", A), ("platform", B)}
