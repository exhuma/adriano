"""
In-memory source adapter test double (the port's second implementation).

:class:`FakeSource` holds projects and files in memory and records every
call, so tests can assert what polling listed and fetched. Failures and
incomplete listings are scripted per project or path.
:class:`FakeSourceType` is a :class:`~app.sources.registry.SourceTypeValidator`
for the ``fake`` type: its ``world`` option names the :class:`FakeSource`
to bind.
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from app.sources.port import (
    DocumentListing,
    FetchedDocument,
    ProjectListing,
    SourceConfigError,
    SourceDocument,
    SourceProject,
    SourceUnavailableError,
)
from app.sources.registry import (
    SourceBinding,
    SourceSettings,
    parse_options,
)


@dataclass
class FakeFile:
    """
    One in-memory file.

    :param content: File bytes.
    :param token: Change token.
    """

    content: bytes
    token: str


@dataclass
class FakeSource:
    """
    In-memory source with scripted failures; implements ``SourceAdapter``.

    :param projects: Project path -> file path -> file.
    :param ref: Published ref reported for every project.
    """

    projects: dict[str, dict[str, FakeFile]] = field(default_factory=dict)
    ref: str = "main"
    fail_projects: bool = False
    projects_complete: bool = True
    fail_listing: set[str] = field(default_factory=set)
    incomplete_listing: set[str] = field(default_factory=set)
    fail_fetch: set[str] = field(default_factory=set)
    unchanged_override: dict[str, str] = field(default_factory=dict)
    fetched: list[str] = field(default_factory=list)
    listed_tokens: dict[str, dict[str, str | None]] = field(
        default_factory=dict
    )
    opened: int = 0

    def put(self, project: str, path: str, content: str, token: str) -> None:
        """
        Add or replace a file.

        :param project: Project path.
        :param path: File path.
        :param content: Text content.
        :param token: Change token.
        """
        self.projects.setdefault(project, {})[path] = FakeFile(
            content.encode(), token
        )

    async def list_projects(self) -> ProjectListing:
        """
        List projects.

        :returns: The listing.
        :raises SourceUnavailableError: When scripted to fail.
        """
        if self.fail_projects:
            raise SourceUnavailableError("fake source is down")
        projects = tuple(
            SourceProject(id=name, path=name, ref=self.ref)
            for name in sorted(self.projects)
        )
        return ProjectListing(
            projects=projects, complete=self.projects_complete
        )

    async def list_documents(
        self,
        project: SourceProject,
        previous_tokens: Mapping[str, str | None],
    ) -> DocumentListing:
        """
        List a project's files; ``changed`` means the token moved.

        Paths in :attr:`unchanged_override` report the given token with
        ``changed=False`` (simulating a moved project-level token).

        :param project: Project.
        :param previous_tokens: Stored tokens.
        :returns: The listing.
        :raises SourceUnavailableError: When scripted to fail.
        """
        self.listed_tokens[project.path] = dict(previous_tokens)
        if project.path in self.fail_listing:
            raise SourceUnavailableError(f"cannot list {project.path}")
        documents = []
        for path, item in sorted(self.projects[project.path].items()):
            if path in self.unchanged_override:
                token, changed = self.unchanged_override[path], False
            else:
                token = item.token
                changed = previous_tokens.get(path) != token
            documents.append(
                SourceDocument(
                    project=project,
                    path=path,
                    change_token=token,
                    changed=changed,
                )
            )
        incomplete = project.path in self.incomplete_listing
        return DocumentListing(
            documents=tuple(documents),
            complete=not incomplete,
            problems=("tree truncated",) if incomplete else (),
        )

    async def fetch(self, document: SourceDocument) -> FetchedDocument:
        """
        Read a file.

        :param document: Document.
        :returns: Its content.
        :raises SourceUnavailableError: When scripted to fail.
        """
        if document.path in self.fail_fetch:
            raise SourceUnavailableError(f"cannot fetch {document.path}")
        self.fetched.append(f"{document.project.path}/{document.path}")
        item = self.projects[document.project.path][document.path]
        return FetchedDocument(
            content=item.content,
            source_url=f"fake://{document.project.path}/{document.path}",
            author="author@example.com",
        )


class _FakeOptions(BaseModel):
    """Type-specific settings of the ``fake`` type."""

    model_config = ConfigDict(extra="forbid")

    world: str


class FakeSourceType:
    """
    Validator of the ``fake`` source type.

    :param worlds: Name -> fake source bound by the ``world`` option.
    """

    def __init__(self, worlds: dict[str, FakeSource]) -> None:
        """
        Store the worlds.

        :param worlds: Name -> fake source.
        """
        self.worlds = worlds

    def __call__(
        self, settings: SourceSettings, env: Mapping[str, str]
    ) -> SourceBinding:
        """
        Bind a fake source.

        :param settings: Common settings plus options.
        :param env: Environment (unused).
        :returns: The binding.
        :raises SourceConfigError: For an unknown world.
        """
        options = parse_options(_FakeOptions, settings.options)
        world = self.worlds.get(options.world)
        if world is None:
            raise SourceConfigError(f"unknown world {options.world!r}")

        @asynccontextmanager
        async def open_adapter() -> AsyncIterator[FakeSource]:
            world.opened += 1
            yield world

        return SourceBinding(open_adapter=open_adapter)
