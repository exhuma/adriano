"""
GitLab source adapter: ADR files on the published branch of projects.

Settings (``catalog.yaml``):

- ``base_url`` -- instance URL (``https://`` only; no credentials,
  query or fragment; ``/api/v4`` is appended internally).
- ``token_env`` -- env var **name** of the access token. A missing or
  empty variable disables the registration; the value is sent only in
  the ``PRIVATE-TOKEN`` header and never logged or echoed.
- ``scope`` -- ``{groups, include_subgroups, projects}``; at least one
  group or project is required (the adapter never lists every visible
  project). ``include_subgroups`` defaults to ``false``.
- ``published_ref`` -- a branch name, or ``"@project-default"`` for each
  project's default branch. Other values starting with ``@`` are
  reserved and rejected.

A project is in scope when its full path is listed in
``scope.projects``, or its parent namespace is a scoped group (any
descendant namespace with ``include_subgroups``). Comparison ignores
case.

Poll steps:

1. :meth:`GitLabAdapter.list_projects` -- paginated, non-archived
   projects of every scoped group (``with_shared=false``) plus each
   explicit project; archived and out-of-scope projects are dropped
   (so a complete listing removes their records), as are empty
   repositories without a default branch. A missing group/project or a
   persistently failing request makes the listing incomplete (nothing
   is deleted); 401/403 fails the poll.
2. :meth:`GitLabAdapter.list_documents` -- reads the branch head. When
   the stored tokens prove nothing changed (see below) all documents
   are reported unchanged without listing the tree. Otherwise the
   recursive tree under ``path`` is listed at the head commit
   (paginated) and a document is ``changed`` only if its ``blob_id``
   differs from the stored one. A missing ADR path (tree 404) is an
   empty, complete listing; a missing branch raises
   :class:`~app.sources.port.SourceNotFoundError`, so polling keeps the
   project's records.
3. :meth:`GitLabAdapter.fetch` -- raw blob by blob id; ``source_url``
   is ``<web_url>/-/blob/<ref>/<path>``. ``author`` is always ``None``:
   the last commit of a file would cost one extra (slow, path-filtered
   commit log) request per changed file, which is not "cheaply
   available".

Change token: ``<blob_id>:<head_sha>:<count>:<path_tag>`` where
``head_sha`` is the branch head the listing was made at, ``count`` the
number of ADR files in that listing and ``path_tag`` the first 12 hex
digits of SHA-256 of the configured ``path``. The tree listing is
skipped only if every stored token of the project carries the current
head and path tag and the number of stored tokens equals ``count``; a
file that failed to fetch, was owned elsewhere or a changed ``path``
therefore forces a full listing on the next poll.

Settings parsing lives in :mod:`app.sources.gitlab_settings`; HTTP
behaviour (retries, backoff, concurrency, timeouts, pagination) in
:mod:`app.sources.gitlab_api`.

Public API: :data:`PROJECT_DEFAULT`, :func:`validate_settings`,
:class:`GitLabScope`, :class:`GitLabAdapter`.
"""

import asyncio
import hashlib
import logging
from collections.abc import AsyncIterator, Awaitable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from app.domain.titles import is_adr_filename
from app.sources.gitlab_api import GitLabApi, Sleep, open_client, parse_model
from app.sources.gitlab_settings import (
    PROJECT_DEFAULT,
    GitLabConfig,
    GitLabScope,
    parse_settings,
)
from app.sources.port import (
    DocumentListing,
    FetchedDocument,
    ProjectListing,
    SourceAccessError,
    SourceDocument,
    SourceError,
    SourceNotFoundError,
    SourceProject,
)
from app.sources.registry import SourceBinding, SourceSettings

__all__ = [
    "PROJECT_DEFAULT",
    "GitLabAdapter",
    "GitLabScope",
    "validate_settings",
]

logger = logging.getLogger(__name__)


def validate_settings(
    settings: SourceSettings,
    env: Mapping[str, str],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    sleep: Sleep = asyncio.sleep,
) -> SourceBinding:
    """
    Validate a ``gitlab`` registration and bind the adapter factory.

    No network I/O happens here (see
    :func:`app.sources.gitlab_settings.parse_settings`); the HTTP
    client is created (and closed) by ``open_adapter`` for each poll.

    :param settings: Common settings plus ``options`` (``base_url``,
        ``token_env``) and ``scope``.
    :param env: Environment used to resolve ``token_env``.
    :param transport: HTTP transport override (tests).
    :param sleep: Async sleep for retry waits (tests).
    :returns: The binding.
    :raises app.sources.port.SourceConfigError: If the settings are
        invalid or the token env var is not set.
    """
    config = parse_settings(settings, env)

    @asynccontextmanager
    async def open_adapter() -> AsyncIterator[GitLabAdapter]:
        client = open_client(
            config.base_url,
            config.token.get_secret_value(),
            transport=transport,
        )
        async with client:
            api = GitLabApi(client, token_env=config.token_env, sleep=sleep)
            yield GitLabAdapter(api=api, config=config)

    return SourceBinding(
        open_adapter=open_adapter, in_scope=config.scope.contains
    )


class _Project(BaseModel):
    """The project fields the adapter reads."""

    id: int
    path_with_namespace: str
    default_branch: str | None = None
    web_url: str | None = None
    archived: bool = False


class _Commit(BaseModel):
    """A commit reference."""

    id: str


class _Branch(BaseModel):
    """The branch fields the adapter reads."""

    commit: _Commit


class _TreeEntry(BaseModel):
    """One repository tree entry."""

    id: str
    path: str
    type: str


@dataclass(frozen=True, slots=True)
class _Token:
    """
    Parsed change token (see the module documentation).

    :param blob_id: Git blob id of the file.
    :param head: Branch head the listing was made at.
    :param count: ADR files in that listing.
    :param path_tag: Tag of the configured ADR path.
    """

    blob_id: str
    head: str
    count: int
    path_tag: str

    def render(self) -> str:
        """
        Format the token.

        :returns: ``<blob_id>:<head>:<count>:<path_tag>``.
        """
        return f"{self.blob_id}:{self.head}:{self.count}:{self.path_tag}"

    @classmethod
    def parse(cls, raw: str | None) -> _Token | None:
        """
        Parse a stored token.

        :param raw: Stored token.
        :returns: The token, or ``None`` if it is not one of ours.
        """
        parts = (raw or "").split(":")
        if len(parts) != 4 or not parts[2].isdigit() or not parts[0]:
            return None
        return cls(parts[0], parts[1], int(parts[2]), parts[3])


def _quoted(value: str) -> str:
    """
    URL-encode a path segment, including ``/``.

    :param value: Raw value (project path, branch name).
    :returns: The encoded segment.
    """
    return quote(value, safe="")


class GitLabAdapter:
    """
    Reads ADR files from the published branch of GitLab projects.

    :param api: API access for this poll.
    :param config: Validated registration settings.
    """

    def __init__(self, *, api: GitLabApi, config: GitLabConfig) -> None:
        """
        Store the settings.

        :param api: API access.
        :param config: Registration settings.
        """
        self._api = api
        self._base_url = config.base_url
        self._scope = config.scope
        self._groups = config.groups
        self._projects = config.projects
        self._path = config.path
        self._published_ref = config.published_ref
        self._path_tag = hashlib.sha256(config.path.encode()).hexdigest()[:12]
        self._web_urls: dict[str, str] = {}

    async def list_projects(self) -> ProjectListing:
        """
        List the non-archived, in-scope projects.

        :returns: The listing; incomplete when a group or project could
            not be read.
        :raises SourceAccessError: If GitLab refuses the token.
        """
        found: dict[int, _Project] = {}
        problems: list[str] = []
        for group in self._groups:
            await self._gather(
                self._group_projects(group), f"group {group}", found, problems
            )
        for path in self._projects:
            await self._gather(
                self._one_project(path), f"project {path}", found, problems
            )
        projects: list[SourceProject] = []
        for item in sorted(found.values(), key=lambda p: p.path_with_namespace):
            source_project = self._source_project(item)
            if source_project is not None:
                projects.append(source_project)
        return ProjectListing(
            projects=tuple(projects),
            complete=not problems,
            problems=tuple(problems),
        )

    async def _gather(
        self,
        request: Awaitable[list[_Project]],
        what: str,
        found: dict[int, _Project],
        problems: list[str],
    ) -> None:
        """
        Add the in-scope, non-archived projects of one request.

        :param request: Pending project request.
        :param what: Description for problems.
        :param found: Projects by id (updated).
        :param problems: Problems (updated).
        :raises SourceAccessError: If GitLab refuses the token.
        """
        try:
            items = await request
        except SourceAccessError:
            raise
        except SourceError as exc:
            problems.append(f"{what}: {exc.message}")
            return
        for item in items:
            if item.archived or not self._scope.contains(
                item.path_with_namespace
            ):
                continue
            found[item.id] = item

    async def _group_projects(self, group: str) -> list[_Project]:
        """
        List the projects of one group (paginated).

        :param group: Group path.
        :returns: The projects.
        """
        url = f"groups/{_quoted(group)}/projects"
        params = {
            "archived": "false",
            "include_subgroups": str(self._scope.include_subgroups).lower(),
            "with_shared": "false",
            "simple": "true",
            "order_by": "id",
            "sort": "asc",
        }
        items = await self._api.get_pages(url, params)
        return [parse_model(_Project, item, url) for item in items]

    async def _one_project(self, path: str) -> list[_Project]:
        """
        Read one explicitly scoped project.

        :param path: Project path.
        :returns: The project as a one-item list.
        """
        url = f"projects/{_quoted(path)}"
        return [parse_model(_Project, await self._api.get_json(url), url)]

    def _source_project(self, item: _Project) -> SourceProject | None:
        """
        Resolve the published ref and remember the web URL.

        :param item: API project.
        :returns: The port project, or ``None`` for an empty repository
            without a default branch.
        """
        ref = self._published_ref
        if ref == PROJECT_DEFAULT:
            if not item.default_branch:
                logger.debug(
                    "skipping %s: no default branch", item.path_with_namespace
                )
                return None
            ref = item.default_branch
        project_id = str(item.id)
        self._web_urls[project_id] = (
            item.web_url or f"{self._base_url}/{item.path_with_namespace}"
        )
        return SourceProject(
            id=project_id, path=item.path_with_namespace, ref=ref
        )

    async def list_documents(
        self,
        project: SourceProject,
        previous_tokens: Mapping[str, str | None],
    ) -> DocumentListing:
        """
        List the ADR files of one project at its branch head.

        :param project: A project from :meth:`list_projects`.
        :param previous_tokens: Stored change token per file path.
        :returns: The listing.
        :raises SourceNotFoundError: If the published branch is missing.
        :raises SourceError: If GitLab cannot be read.
        """
        head = await self._branch_head(project)
        skipped = self._unchanged(project, previous_tokens, head)
        if skipped is not None:
            return skipped
        entries = await self._tree(project, head)
        count = len(entries)
        documents: list[SourceDocument] = []
        for entry in entries:
            token = _Token(entry.id, head, count, self._path_tag)
            stored = _Token.parse(previous_tokens.get(entry.path))
            documents.append(
                SourceDocument(
                    project=project,
                    path=entry.path,
                    change_token=token.render(),
                    changed=stored is None or stored.blob_id != entry.id,
                )
            )
        return DocumentListing(documents=tuple(documents))

    async def _branch_head(self, project: SourceProject) -> str:
        """
        Read the head commit of the published branch.

        :param project: The project.
        :returns: The commit id.
        :raises SourceNotFoundError: If the branch does not exist.
        """
        url = (
            f"projects/{project.id}/repository/branches/{_quoted(project.ref)}"
        )
        try:
            data = await self._api.get_json(url)
        except SourceNotFoundError as exc:
            raise SourceNotFoundError(
                f"published ref {project.ref!r} of {project.path} not found"
            ) from exc
        return parse_model(_Branch, data, url).commit.id

    def _unchanged(
        self,
        project: SourceProject,
        previous_tokens: Mapping[str, str | None],
        head: str,
    ) -> DocumentListing | None:
        """
        Build the listing of an unchanged branch from stored tokens.

        :param project: The project.
        :param previous_tokens: Stored tokens by path.
        :param head: Current branch head.
        :returns: All stored documents as unchanged, or ``None`` if the
            tokens do not prove that the last listing was fully stored
            at this head and path.
        """
        if not previous_tokens:
            return None
        for raw in previous_tokens.values():
            token = _Token.parse(raw)
            if (
                token is None
                or token.head != head
                or token.path_tag != self._path_tag
                or token.count != len(previous_tokens)
            ):
                return None
        logger.debug("%s: branch head unchanged; tree skipped", project.path)
        return DocumentListing(
            documents=tuple(
                SourceDocument(
                    project=project, path=path, change_token=raw, changed=False
                )
                for path, raw in previous_tokens.items()
            )
        )

    async def _tree(
        self, project: SourceProject, head: str
    ) -> list[_TreeEntry]:
        """
        List the ADR blobs under ``path`` at ``head`` (paginated).

        :param project: The project.
        :param head: Commit to list.
        :returns: ADR file entries; empty if ``path`` does not exist.
        """
        url = f"projects/{project.id}/repository/tree"
        params = {"ref": head, "recursive": "true", "pagination": "keyset"}
        if self._path:
            params["path"] = self._path
        try:
            items = await self._api.get_pages(url, params)
        except SourceNotFoundError:
            return []
        entries = [parse_model(_TreeEntry, item, url) for item in items]
        return [
            entry
            for entry in entries
            if entry.type == "blob" and is_adr_filename(entry.path)
        ]

    async def fetch(self, document: SourceDocument) -> FetchedDocument:
        """
        Read one document's raw blob.

        :param document: A document from :meth:`list_documents`.
        :returns: Its exact bytes and web URL; ``author`` is ``None``.
        :raises SourceError: If the blob cannot be read.
        """
        token = _Token.parse(document.change_token)
        if token is None:
            raise SourceError(
                f"{document.path}: no blob id in the listing; relist"
            )
        project = document.project
        url = f"projects/{project.id}/repository/blobs/{token.blob_id}/raw"
        response = await self._api.get(url)
        web_url = self._web_urls.get(
            project.id, f"{self._base_url}/{project.path}"
        )
        source_url = (
            f"{web_url}/-/blob/{quote(project.ref, safe='/')}/"
            f"{quote(document.path, safe='/')}"
        )
        return FetchedDocument(content=response.content, source_url=source_url)
