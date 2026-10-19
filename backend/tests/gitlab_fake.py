"""
In-memory GitLab REST API v4 served through ``httpx.MockTransport``.

:class:`FakeGitLab` implements the few endpoints the GitLab adapter
uses (group projects, single project, branch, recursive tree, raw
blob) with real-looking pagination: group projects use offset pages
announced only by ``X-Next-Page``; the tree uses keyset pages announced
only by a ``Link: <...>; rel="next"`` header. Every request is logged
and failures are scripted per route, so tests can assert what was
called and how retries behave. No network is involved.
"""

import hashlib
import itertools
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote

import httpx

BASE_URL = "https://gitlab.test"
API = f"{BASE_URL}/api/v4/"
TOKEN = "glpat-super-secret-value"

_ids = itertools.count(1)


def blob_id(content: bytes) -> str:
    """
    Compute a git-style blob id.

    :param content: File bytes.
    :returns: The hex id.
    """
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


@dataclass
class FakeRepo:
    """
    One project with one branch whose head moves on every change.

    :param path: Full project path.
    :param default_branch: Default branch (``None`` = empty repo).
    :param archived: Archived flag.
    """

    path: str
    default_branch: str | None = "main"
    archived: bool = False
    id: int = field(default_factory=lambda: next(_ids))
    files: dict[str, bytes] = field(default_factory=dict)
    head: str = field(default_factory=lambda: f"c{next(_ids):039d}")

    def put(self, path: str, text: str) -> None:
        """
        Commit a file (moves the head).

        :param path: File path.
        :param text: Content.
        """
        self.files[path] = text.encode()
        self.commit()

    def remove(self, path: str) -> None:
        """
        Commit a deletion (moves the head).

        :param path: File path.
        """
        del self.files[path]
        self.commit()

    def commit(self) -> None:
        """Move the branch head without changing files."""
        self.head = f"c{next(_ids):039d}"


@dataclass
class FakeGitLab:
    """
    Scriptable fake GitLab instance.

    :param page_size: Upper bound of items per page (forces paging).
    """

    page_size: int = 100
    repos: dict[str, FakeRepo] = field(default_factory=dict)
    groups: set[str] = field(default_factory=set)
    #: Extra items returned by every group listing (e.g. out of scope).
    stray: list[FakeRepo] = field(default_factory=list)
    #: Route -> statuses returned (in order) before normal answers.
    script: dict[str, list[int]] = field(default_factory=dict)
    #: Routes that always answer 503.
    down: set[str] = field(default_factory=set)
    retry_after: str | None = None
    requests: list[httpx.Request] = field(default_factory=list)

    def repo(
        self,
        path: str,
        *,
        default_branch: str | None = "main",
        archived: bool = False,
    ) -> FakeRepo:
        """
        Create a project and register its namespace as a group.

        :param path: Full project path.
        :param default_branch: Default branch.
        :param archived: Archived flag.
        :returns: The repo.
        """
        repo = FakeRepo(path, default_branch, archived)
        self.repos[path] = repo
        self.groups.add(path.rpartition("/")[0])
        return repo

    def transport(self) -> httpx.MockTransport:
        """
        Build the transport serving this instance.

        :returns: The transport.
        """
        return httpx.MockTransport(self.handle)

    def calls(self, route: str) -> int:
        """
        Count requests of one route.

        :param route: Route name (see :meth:`_route`).
        :returns: The count.
        """
        return sum(1 for r in self.requests if self._route(r)[0] == route)

    def handle(self, request: httpx.Request) -> httpx.Response:
        """
        Answer one request.

        :param request: The request.
        :returns: The response.
        """
        self.requests.append(request)
        if request.headers.get("PRIVATE-TOKEN") != TOKEN:
            return httpx.Response(401, json={"message": "401 Unauthorized"})
        route, args = self._route(request)
        scripted = self.script.get(route)
        if scripted:
            return self._error(scripted.pop(0))
        if route in self.down:
            return self._error(503)
        handler = getattr(self, f"_{route}", None)
        if handler is None:
            return httpx.Response(404, json={"message": "404 Not Found"})
        return handler(request, *args)

    def _error(self, status: int) -> httpx.Response:
        """
        Build a scripted error response.

        :param status: HTTP status.
        :returns: The response.
        """
        headers = {}
        if status == 429 and self.retry_after is not None:
            headers["Retry-After"] = self.retry_after
        return httpx.Response(status, headers=headers, json={"message": "x"})

    @staticmethod
    def _route(request: httpx.Request) -> tuple[str, list[str]]:
        """
        Map a request to a route name and decoded arguments.

        :param request: The request.
        :returns: ``(route, args)``.
        """
        raw = request.url.raw_path.decode().split("?")[0]
        parts = [unquote(p) for p in raw.removeprefix("/api/v4/").split("/")]
        match parts:
            case ["groups", group, "projects"]:
                return "groups", [group]
            case ["projects", project]:
                return "project", [project]
            case ["projects", pid, "repository", "branches", branch]:
                return "branch", [pid, branch]
            case ["projects", pid, "repository", "tree"]:
                return "tree", [pid]
            case ["projects", pid, "repository", "blobs", sha, "raw"]:
                return "blob", [pid, sha]
        return "unknown", []

    def _by_id(self, pid: str) -> FakeRepo | None:
        """
        Find a repo by numeric id.

        :param pid: Id as text.
        :returns: The repo, if any.
        """
        return next((r for r in self.repos.values() if str(r.id) == pid), None)

    @staticmethod
    def _json(repo: FakeRepo) -> dict[str, object]:
        """
        Render a project.

        :param repo: The repo.
        :returns: API JSON.
        """
        return {
            "id": repo.id,
            "path_with_namespace": repo.path,
            "default_branch": repo.default_branch,
            "web_url": f"{BASE_URL}/{repo.path}",
            "archived": repo.archived,
        }

    def _groups(self, request: httpx.Request, group: str) -> httpx.Response:
        """
        List a group's projects (offset pages, ``X-Next-Page`` only).

        :param request: The request.
        :param group: Group path.
        :returns: The response.
        """
        query = parse_qs(request.url.query.decode())
        if group not in self.groups:
            return httpx.Response(404, json={"message": "404 Group"})
        subgroups = query.get("include_subgroups") == ["true"]
        archived = query.get("archived") == ["false"]
        items = [
            r
            for r in sorted(self.repos.values(), key=lambda r: r.id)
            if (
                r.path.rpartition("/")[0] == group
                or (subgroups and r.path.startswith(group + "/"))
            )
            and not (archived and r.archived)
        ] + self.stray
        per_page = min(int(query["per_page"][0]), self.page_size)
        page = int(query.get("page", ["1"])[0])
        chunk = items[(page - 1) * per_page : page * per_page]
        more = page * per_page < len(items)
        headers = {"X-Next-Page": str(page + 1) if more else ""}
        body = [self._json(r) for r in chunk]
        return httpx.Response(200, headers=headers, json=body)

    def _project(self, request: httpx.Request, path: str) -> httpx.Response:
        """
        Read one project by path.

        :param request: The request.
        :param path: Project path.
        :returns: The response.
        """
        del request
        repo = self.repos.get(path)
        if repo is None:
            return httpx.Response(404, json={"message": "404 Project"})
        return httpx.Response(200, json=self._json(repo))

    def _branch(
        self, request: httpx.Request, pid: str, branch: str
    ) -> httpx.Response:
        """
        Read one branch.

        :param request: The request.
        :param pid: Project id.
        :param branch: Branch name.
        :returns: The response.
        """
        del request
        repo = self._by_id(pid)
        if repo is None or branch != repo.default_branch:
            return httpx.Response(404, json={"message": "404 Branch"})
        return httpx.Response(
            200, json={"name": branch, "commit": {"id": repo.head}}
        )

    def _tree(self, request: httpx.Request, pid: str) -> httpx.Response:
        """
        List a recursive tree (keyset pages, ``Link`` header only).

        :param request: The request.
        :param pid: Project id.
        :returns: The response.
        """
        repo = self._by_id(pid)
        query = parse_qs(request.url.query.decode())
        prefix = query.get("path", [""])[0]
        if repo is None or query.get("ref") != [repo.head]:
            return httpx.Response(404, json={"message": "404 Tree"})
        paths = sorted(p for p in repo.files if p.startswith(prefix + "/"))
        if not paths:
            return httpx.Response(404, json={"message": "404 Tree Not Found"})
        start = int(query.get("page_token", ["0"])[0])
        per_page = min(int(query.get("per_page", ["20"])[0]), self.page_size)
        chunk = paths[start : start + per_page]
        body = [
            {"id": blob_id(repo.files[p]), "path": p, "type": "blob"}
            for p in chunk
        ] + [{"id": "t" * 40, "path": prefix, "type": "tree"}]
        headers = {}
        if start + per_page < len(paths):
            nxt = request.url.copy_merge_params(
                {"page_token": str(start + per_page)}
            )
            headers["Link"] = f'<{nxt}>; rel="next"'
        return httpx.Response(200, headers=headers, json=body)

    def _blob(
        self, request: httpx.Request, pid: str, sha: str
    ) -> httpx.Response:
        """
        Read a raw blob.

        :param request: The request.
        :param pid: Project id.
        :param sha: Blob id.
        :returns: The response.
        """
        del request
        repo = self._by_id(pid)
        for content in repo.files.values() if repo else ():
            if blob_id(content) == sha:
                return httpx.Response(200, content=content)
        return httpx.Response(404, json={"message": "404 Blob"})
