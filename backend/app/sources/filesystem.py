"""
Filesystem source adapter: ADR files in a directory tree on disk.

Each immediate subdirectory of the configured ``root`` is a project
(optionally filtered by ``scope.projects``). ADR files are discovered
recursively under the registration ``path`` inside each project, using
the legacy filename pattern (:func:`app.domain.titles.is_adr_filename`).
The change token is ``<mtime_ns>:<size>`` from :func:`os.stat`, so an
unchanged file is never re-read. Directory walks and reads run in a
worker thread via :func:`asyncio.to_thread`, since :mod:`pathlib` and
:mod:`os` are blocking.

There is no ``file://`` URL: :meth:`FilesystemAdapter.fetch` returns
the absolute on-disk path as a human-readable ``source_url`` instead.
It is shown only to operators with filesystem access, so a plain path
is the most useful "link" available; ``author`` is always ``None``
(the filesystem has no commit/push metadata).

An unreadable or missing ``root`` raises :class:`SourceNotFoundError`
or :class:`SourceAccessError` from
:meth:`FilesystemAdapter.list_projects`, which fails the whole poll
(the port contract then deletes nothing). A project's ADR directory
that is simply absent is not an error (no files); one that exists but
cannot be listed (or whose walk hits an unreadable subdirectory) is
reported as an incomplete document listing for that project only, so
polling preserves its stored records.

Public API: :func:`validate_settings`, :class:`FilesystemAdapter`.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from app.domain.titles import is_adr_filename
from app.sources.port import (
    DocumentListing,
    FetchedDocument,
    ProjectListing,
    SourceAccessError,
    SourceDocument,
    SourceNotFoundError,
    SourceProject,
    SourceUnavailableError,
)
from app.sources.registry import SourceBinding, SourceSettings, parse_options

__all__ = ["FilesystemAdapter", "validate_settings"]


class _Options(BaseModel):
    """Type-specific settings of the ``filesystem`` type."""

    model_config = ConfigDict(extra="forbid")

    root: str


class _Scope(BaseModel):
    """``scope`` of a ``filesystem`` registration."""

    model_config = ConfigDict(extra="forbid")

    projects: list[str] = Field(default_factory=list)


def validate_settings(
    settings: SourceSettings, env: Mapping[str, str]
) -> SourceBinding:
    """
    Validate ``root`` and ``scope.projects``; bind the adapter factory.

    No filesystem I/O happens here; ``root`` is only resolved against
    ``settings.base_dir`` when relative.

    :param settings: Common settings plus ``options`` (``root``) and
        ``scope`` (``projects``, optional).
    :param env: Unused; the filesystem adapter needs no secrets.
    :returns: The binding.
    :raises app.sources.port.SourceConfigError: If ``root`` or ``scope``
        are invalid.
    """
    del env
    options = parse_options(_Options, settings.options)
    scope = parse_options(_Scope, settings.scope, prefix="scope")
    raw_root = Path(options.root)
    root = raw_root if raw_root.is_absolute() else settings.base_dir / raw_root
    projects = frozenset(scope.projects)

    def in_scope(project: str) -> bool:
        return not projects or project in projects

    @asynccontextmanager
    async def open_adapter() -> AsyncIterator[FilesystemAdapter]:
        yield FilesystemAdapter(
            root=root,
            path=settings.path,
            published_ref=settings.published_ref,
            projects=projects,
        )

    return SourceBinding(open_adapter=open_adapter, in_scope=in_scope)


def _scan_root(root: Path) -> list[str]:
    """
    List the immediate subdirectory names of ``root``.

    :param root: Root directory.
    :returns: Sorted directory names (broken entries skipped).
    :raises OSError: If ``root`` itself cannot be listed.
    """
    names: list[str] = []
    with os.scandir(root) as entries:
        for entry in entries:
            try:
                if entry.is_dir():
                    names.append(entry.name)
            except OSError:
                continue
    return sorted(names)


def _stat_token(path: Path) -> str | None:
    """
    Build the change token of one file.

    :param path: File path.
    :returns: ``"<mtime_ns>:<size>"``, or ``None`` if it cannot be
        statted (the caller records a problem).
    """
    try:
        info = path.stat()
    except OSError:
        return None
    return f"{info.st_mtime_ns}:{info.st_size}"


def _walk_adr_files(base: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """
    Walk one project's ADR directory synchronously.

    A missing ``base`` is not an error (the project simply has no ADR
    files yet); only existing-but-unreadable directories report a
    problem.

    :param base: Absolute directory to walk (project path + configured
        ADR path).
    :returns: ``(entries, problems)``; entries are ``(relative POSIX
        path, change token)`` pairs for files whose basename matches
        :func:`~app.domain.titles.is_adr_filename`.
    """
    try:
        with os.scandir(base):
            pass
    except FileNotFoundError:
        return [], []
    except NotADirectoryError:
        return [], []
    except OSError as exc:
        return [], [f"cannot read {base}: {exc}"]

    problems: list[str] = []

    def onerror(exc: OSError) -> None:
        problems.append(f"cannot read {exc.filename}: {exc}")

    entries: list[tuple[str, str]] = []
    for dirpath, _dirnames, filenames in os.walk(base, onerror=onerror):
        for name in filenames:
            if not is_adr_filename(name):
                continue
            full = Path(dirpath, name)
            token = _stat_token(full)
            if token is None:
                problems.append(f"cannot read {full}")
                continue
            rel = full.relative_to(base).as_posix()
            entries.append((rel, token))
    return entries, problems


@dataclass(frozen=True, slots=True, kw_only=True)
class FilesystemAdapter:
    """
    Reads ADR files from a directory tree on disk.

    :param root: Root directory (one immediate subdirectory per
        project); may be relative to the process working directory
        only if the caller already resolved it.
    :param path: ADR path inside each project (POSIX, relative;
        possibly empty for the project root).
    :param published_ref: Ref label reported for every project (the
        registration's configured ``published_ref``; the filesystem has
        no real refs).
    :param projects: Project names to include; empty means every
        immediate subdirectory of ``root``.
    """

    root: Path
    path: str
    published_ref: str
    projects: frozenset[str] = frozenset()

    async def list_projects(self) -> ProjectListing:
        """
        List the in-scope immediate subdirectories of ``root``.

        :returns: The listing (always complete; a problem here instead
            raises).
        :raises SourceNotFoundError: If ``root`` does not exist or is
            not a directory.
        :raises SourceAccessError: If ``root`` is not readable.
        :raises SourceUnavailableError: For any other listing failure.
        """
        names = await asyncio.to_thread(self._scan_root_checked)
        in_scope = self._project_filter()
        projects = tuple(
            SourceProject(id=name, path=name, ref=self.published_ref)
            for name in names
            if in_scope(name)
        )
        return ProjectListing(projects=projects)

    def _project_filter(self) -> Callable[[str], bool]:
        """
        Build the scope predicate for :meth:`list_projects`.

        :returns: A callable accepting an in-scope project name.
        """
        projects = self.projects
        return lambda name: not projects or name in projects

    def _scan_root_checked(self) -> list[str]:
        """
        List ``root``'s subdirectories, translating ``OSError``.

        :returns: Sorted directory names.
        :raises SourceNotFoundError: Missing or not a directory.
        :raises SourceAccessError: Permission denied.
        :raises SourceUnavailableError: Any other ``OSError``.
        """
        try:
            return _scan_root(self.root)
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise SourceNotFoundError(
                f"filesystem root {self.root} does not exist or is not a "
                "directory"
            ) from exc
        except PermissionError as exc:
            raise SourceAccessError(
                f"filesystem root {self.root} is not readable"
            ) from exc
        except OSError as exc:
            raise SourceUnavailableError(
                f"cannot list filesystem root {self.root}: {exc}"
            ) from exc

    async def list_documents(
        self,
        project: SourceProject,
        previous_tokens: Mapping[str, str | None],
    ) -> DocumentListing:
        """
        List the ADR files of one project.

        :param project: A project from :meth:`list_projects`.
        :param previous_tokens: Stored change token per file path.
        :returns: The listing; ``complete=False`` with a problem if the
            project's ADR directory exists but could not be fully read.
        """
        base = self.root / project.path / self.path
        entries, problems = await asyncio.to_thread(_walk_adr_files, base)
        documents = tuple(
            self._document(project, rel, token, previous_tokens)
            for rel, token in entries
        )
        return DocumentListing(
            documents=documents,
            complete=not problems,
            problems=tuple(problems),
        )

    def _document(
        self,
        project: SourceProject,
        rel: str,
        token: str,
        previous_tokens: Mapping[str, str | None],
    ) -> SourceDocument:
        """
        Build one document, flagging it changed against its stored token.

        :param project: Owning project.
        :param rel: File path relative to the configured ADR directory.
        :param token: Freshly computed change token.
        :param previous_tokens: Stored change token per file path.
        :returns: The document.
        """
        path = str(PurePosixPath(self.path) / rel)
        return SourceDocument(
            project=project,
            path=path,
            change_token=token,
            changed=previous_tokens.get(path) != token,
        )

    async def fetch(self, document: SourceDocument) -> FetchedDocument:
        """
        Read one document's exact bytes.

        :param document: A document from :meth:`list_documents`.
        :returns: Its content; ``source_url`` is the absolute path on
            disk (there is no ``file://`` URL); ``author`` is always
            ``None``.
        :raises SourceNotFoundError: If the file no longer exists.
        :raises SourceAccessError: If it is not readable.
        :raises SourceUnavailableError: For any other read failure.
        """
        full = self.root / document.project.path / document.path
        try:
            content = await asyncio.to_thread(full.read_bytes)
        except FileNotFoundError as exc:
            raise SourceNotFoundError(f"{full} no longer exists") from exc
        except PermissionError as exc:
            raise SourceAccessError(f"{full} is not readable") from exc
        except OSError as exc:
            raise SourceUnavailableError(f"cannot read {full}: {exc}") from exc
        return FetchedDocument(content=content, source_url=str(full))
