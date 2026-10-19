"""Unit tests for the filesystem source adapter (no database)."""

import os
import uuid
from pathlib import Path

import pytest

from app.domain.frontmatter import JsonValue
from app.sources.filesystem import FilesystemAdapter, validate_settings
from app.sources.port import (
    SourceAccessError,
    SourceConfigError,
    SourceDocument,
    SourceNotFoundError,
    SourceProject,
)
from app.sources.registry import SourceSettings


def settings(
    tmp_path: Path,
    *,
    root: str = "root",
    scope: dict[str, JsonValue] | None = None,
    path: str = "doc/decisions",
    options_extra: dict[str, JsonValue] | None = None,
) -> SourceSettings:
    """
    Build minimal common settings for :func:`validate_settings`.

    :param tmp_path: Base directory for relative paths.
    :param root: ``root`` option (omitted entirely if ``None``).
    :param scope: Raw ``scope`` mapping.
    :param path: ADR path.
    :param options_extra: Extra keys merged into ``options``.
    :returns: The settings.
    """
    options: dict[str, JsonValue] = {"root": root}
    options.update(options_extra or {})
    return SourceSettings(
        id="fs",
        type="filesystem",
        path=path,
        published_ref="local",
        scope=scope or {},
        options=options,
        base_dir=tmp_path,
    )


def adr(title: str) -> str:
    """
    Build a minimal valid ADR document.

    :param title: Title.
    :returns: The document text.
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


def test_validate_settings_requires_root(tmp_path: Path) -> None:
    """Ensure a missing `root` option is a readable config error."""
    broken = SourceSettings(
        id="fs",
        type="filesystem",
        path="doc/decisions",
        published_ref="local",
        scope={},
        options={},
        base_dir=tmp_path,
    )

    with pytest.raises(SourceConfigError, match="root"):
        validate_settings(broken, {})


def test_validate_settings_rejects_unknown_option(tmp_path: Path) -> None:
    """Ensure an unknown option is rejected (``extra="forbid"``)."""
    bad = settings(tmp_path, options_extra={"surprise": 1})

    with pytest.raises(SourceConfigError, match="surprise"):
        validate_settings(bad, {})


def test_validate_settings_rejects_unknown_scope_key(tmp_path: Path) -> None:
    """Ensure an unknown scope key (not ``projects``) is rejected."""
    bad = settings(tmp_path, scope={"groups": ["x"]})

    with pytest.raises(SourceConfigError, match="scope"):
        validate_settings(bad, {})


async def test_validate_settings_resolves_relative_root(
    tmp_path: Path,
) -> None:
    """Ensure a relative root resolves against ``base_dir``, no I/O."""
    binding = validate_settings(settings(tmp_path, root="sub/root"), {})

    async with binding.open_adapter() as adapter:
        assert isinstance(adapter, FilesystemAdapter)
        assert adapter.root == tmp_path / "sub/root"


async def test_validate_settings_keeps_absolute_root(tmp_path: Path) -> None:
    """Ensure an absolute root is kept unchanged."""
    absolute = tmp_path / "elsewhere"
    binding = validate_settings(settings(tmp_path, root=str(absolute)), {})

    async with binding.open_adapter() as adapter:
        assert isinstance(adapter, FilesystemAdapter)
        assert adapter.root == absolute


def test_in_scope_predicate_matches_scope_projects(tmp_path: Path) -> None:
    """Ensure the push-intake scope predicate matches ``scope.projects``."""
    binding = validate_settings(
        settings(tmp_path, scope={"projects": ["platform"]}), {}
    )

    assert binding.in_scope("platform") is True
    assert binding.in_scope("payments") is False


def test_in_scope_predicate_accepts_everything_by_default(
    tmp_path: Path,
) -> None:
    """Ensure an empty (or absent) scope accepts every project."""
    binding = validate_settings(settings(tmp_path), {})

    assert binding.in_scope("anything") is True


async def test_list_projects_lists_subdirectories_sorted_and_filtered(
    tmp_path: Path,
) -> None:
    """Ensure listing finds immediate subdirectories, filtered by scope."""
    (tmp_path / "zeta").mkdir()
    (tmp_path / "alpha").mkdir()
    (tmp_path / "ignored.txt").write_text("x", encoding="utf-8")
    adapter = FilesystemAdapter(
        root=tmp_path,
        path="doc/decisions",
        published_ref="local",
        projects=frozenset({"alpha", "zeta"}),
    )

    listing = await adapter.list_projects()

    assert listing.complete
    assert [p.path for p in listing.projects] == ["alpha", "zeta"]
    assert all(p.ref == "local" for p in listing.projects)


async def test_list_projects_raises_for_missing_root(tmp_path: Path) -> None:
    """Ensure a missing root raises :class:`SourceNotFoundError`."""
    adapter = FilesystemAdapter(
        root=tmp_path / "nope", path="doc/decisions", published_ref="local"
    )

    with pytest.raises(SourceNotFoundError):
        await adapter.list_projects()


async def test_list_projects_raises_for_unreadable_root(
    tmp_path: Path,
) -> None:
    """Ensure a permission-denied root raises :class:`SourceAccessError`."""
    if os.geteuid() == 0:
        pytest.skip("root bypasses permission checks")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o000)
    adapter = FilesystemAdapter(
        root=locked, path="doc/decisions", published_ref="local"
    )

    try:
        with pytest.raises(SourceAccessError):
            await adapter.list_projects()
    finally:
        locked.chmod(0o755)


async def test_list_documents_discovers_recursively_and_ignores_non_adr(
    tmp_path: Path,
) -> None:
    """Ensure discovery recurses and the legacy filename regex applies."""
    project = SourceProject(id="platform", path="platform", ref="local")
    write(tmp_path / "platform/doc/decisions/2024-01-01-a.md", adr("A"))
    write(tmp_path / "platform/doc/decisions/sub/2024-01-02-b.md", adr("B"))
    write(tmp_path / "platform/doc/decisions/README.md", "# not an adr")
    write(tmp_path / "platform/doc/decisions/not-a-date.md", adr("C"))
    adapter = FilesystemAdapter(
        root=tmp_path, path="doc/decisions", published_ref="local"
    )

    listing = await adapter.list_documents(project, {})

    assert listing.complete
    assert sorted(d.path for d in listing.documents) == [
        "doc/decisions/2024-01-01-a.md",
        "doc/decisions/sub/2024-01-02-b.md",
    ]
    assert all(d.changed for d in listing.documents)


async def test_list_documents_reports_changed_against_stored_tokens(
    tmp_path: Path,
) -> None:
    """Ensure ``changed`` reflects a mismatch against a stored token."""
    project = SourceProject(id="platform", path="platform", ref="local")
    write(tmp_path / "platform/doc/decisions/2024-01-01-a.md", adr("A"))
    adapter = FilesystemAdapter(
        root=tmp_path, path="doc/decisions", published_ref="local"
    )
    (found,) = (await adapter.list_documents(project, {})).documents

    same = await adapter.list_documents(
        project, {found.path: found.change_token}
    )
    stale = await adapter.list_documents(project, {found.path: "x"})

    assert same.documents[0].changed is False
    assert stale.documents[0].changed is True


async def test_list_documents_missing_adr_directory_is_empty_not_an_error(
    tmp_path: Path,
) -> None:
    """Ensure a project without the configured ADR path yields no files."""
    (tmp_path / "platform").mkdir()
    project = SourceProject(id="platform", path="platform", ref="local")
    adapter = FilesystemAdapter(
        root=tmp_path, path="doc/decisions", published_ref="local"
    )

    listing = await adapter.list_documents(project, {})

    assert listing.complete
    assert listing.documents == ()


async def test_list_documents_reports_incomplete_for_unreadable_directory(
    tmp_path: Path,
) -> None:
    """Ensure an unreadable ADR directory is incomplete, with a problem."""
    if os.geteuid() == 0:
        pytest.skip("root bypasses permission checks")
    project = SourceProject(id="platform", path="platform", ref="local")
    decisions = tmp_path / "platform/doc/decisions"
    decisions.mkdir(parents=True)
    decisions.chmod(0o000)
    adapter = FilesystemAdapter(
        root=tmp_path, path="doc/decisions", published_ref="local"
    )

    try:
        listing = await adapter.list_documents(project, {})
    finally:
        decisions.chmod(0o755)

    assert listing.complete is False
    assert listing.problems


async def test_fetch_returns_bytes_and_a_display_path(
    tmp_path: Path,
) -> None:
    """Ensure fetch reads bytes and reports a readable (non-URL) path."""
    project = SourceProject(id="platform", path="platform", ref="local")
    file_path = tmp_path / "platform/doc/decisions/2024-01-01-a.md"
    text = adr("A")
    write(file_path, text)
    adapter = FilesystemAdapter(
        root=tmp_path, path="doc/decisions", published_ref="local"
    )
    (found,) = (await adapter.list_documents(project, {})).documents

    fetched = await adapter.fetch(found)

    assert fetched.content == text.encode()
    assert fetched.author is None
    assert fetched.source_url == str(file_path)
    assert "file://" not in (fetched.source_url or "")


async def test_fetch_raises_not_found_for_a_missing_file(
    tmp_path: Path,
) -> None:
    """Ensure fetch raises :class:`SourceNotFoundError` for a gone file."""
    project = SourceProject(id="platform", path="platform", ref="local")
    adapter = FilesystemAdapter(
        root=tmp_path, path="doc/decisions", published_ref="local"
    )
    document = SourceDocument(
        project=project, path="doc/decisions/gone.md", change_token=None
    )

    with pytest.raises(SourceNotFoundError):
        await adapter.fetch(document)
