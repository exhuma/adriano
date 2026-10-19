"""Unit tests for the GitLab source adapter (``httpx.MockTransport``)."""

import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from app.domain.frontmatter import JsonValue
from app.sources import gitlab_api
from app.sources.gitlab import GitLabAdapter, validate_settings
from app.sources.port import (
    SourceAccessError,
    SourceConfigError,
    SourceNotFoundError,
    SourceProject,
    SourceUnavailableError,
)
from app.sources.registry import SourceSettings
from tests.gitlab_fake import BASE_URL, TOKEN, FakeGitLab

ENV = {"GL_TOKEN": TOKEN}
ADR = "doc/decisions/2024-01-01-a.md"
ADR_B = "doc/decisions/sub/2024-01-02-b.md"


def adr(title: str) -> str:
    """
    Build a valid ADR document.

    :param title: Title.
    :returns: The text.
    """
    return f"---\nuuid: {uuid.uuid4()}\ntitle: {title}\n---\nBody.\n"


def settings(
    *,
    scope: Mapping[str, JsonValue] | None = None,
    published_ref: str = "@project-default",
    **options: JsonValue,
) -> SourceSettings:
    """
    Build ``gitlab`` settings.

    :param scope: Raw scope (default: group ``platform``).
    :param published_ref: Published ref.
    :param options: Option overrides.
    :returns: The settings.
    """
    merged: dict[str, JsonValue] = {
        "base_url": BASE_URL,
        "token_env": "GL_TOKEN",
    }
    merged.update(options)
    return SourceSettings(
        id="gl",
        type="gitlab",
        path="doc/decisions",
        published_ref=published_ref,
        scope=scope if scope is not None else {"groups": ["platform"]},
        options=merged,
        base_dir=Path("."),
    )


class Sleeps:
    """Records retry waits instead of sleeping."""

    def __init__(self) -> None:
        """Start empty."""
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        """
        Record one wait.

        :param seconds: Requested wait.
        """
        self.waits.append(seconds)


@asynccontextmanager
async def opened(
    fake: FakeGitLab, sleeps: Sleeps | None = None, **kwargs: JsonValue
) -> AsyncIterator[GitLabAdapter]:
    """
    Open an adapter served by the fake.

    :param fake: Fake GitLab.
    :param sleeps: Sleep recorder.
    :param kwargs: :func:`settings` arguments.
    :returns: The adapter (context manager).
    """
    binding = validate_settings(
        settings(**kwargs),  # type: ignore[arg-type]
        ENV,
        transport=fake.transport(),
        sleep=sleeps or Sleeps(),
    )
    async with binding.open_adapter() as adapter:
        assert isinstance(adapter, GitLabAdapter)
        yield adapter


def project(fake: FakeGitLab, path: str) -> SourceProject:
    """
    Build the port project of a fake repo.

    :param fake: Fake GitLab.
    :param path: Project path.
    :returns: The project.
    """
    repo = fake.repos[path]
    return SourceProject(id=str(repo.id), path=path, ref="main")


@pytest.mark.parametrize(
    ("env", "overrides", "match"),
    [
        ({}, {}, "GL_TOKEN is not set"),
        ({"GL_TOKEN": ""}, {}, "GL_TOKEN is not set"),
        (ENV, {"base_url": "http://gitlab.test"}, "https"),
        (ENV, {"base_url": "https://u:p@gitlab.test"}, "credentials"),
        (ENV, {"surprise": 1}, "surprise"),
        (ENV, {"scope": {}}, "at least one group or project"),
        (ENV, {"scope": {"teams": ["x"]}}, "scope"),
        (ENV, {"published_ref": "@latest"}, "published_ref"),
    ],
)
def test_validate_settings_rejects_invalid_settings(
    env: dict[str, str], overrides: dict[str, JsonValue], match: str
) -> None:
    """Ensure invalid gitlab settings are readable config errors."""
    with pytest.raises(SourceConfigError, match=match) as caught:
        validate_settings(settings(**overrides), env)  # type: ignore[arg-type]

    assert TOKEN not in caught.value.message
    assert "u:p" not in caught.value.message


def test_in_scope_matches_projects_groups_and_subgroups() -> None:
    """Ensure the scope predicate follows groups, subgroups and projects."""
    flat = validate_settings(
        settings(scope={"groups": ["Platform"], "projects": ["x/one"]}), ENV
    )
    deep = validate_settings(
        settings(scope={"groups": ["platform"], "include_subgroups": True}),
        ENV,
    )

    assert flat.in_scope("platform/api")
    assert flat.in_scope("x/one")
    assert not flat.in_scope("platform/sub/api")
    assert not flat.in_scope("x/two")
    assert not flat.in_scope("platformer/api")
    assert deep.in_scope("platform/sub/api")
    assert not deep.in_scope("other/api")


async def test_list_projects_paginates_and_filters() -> None:
    """Ensure paging, archived/out-of-scope/empty exclusion and refs."""
    fake = FakeGitLab(page_size=2)
    for name in ("a", "b", "c"):
        fake.repo(f"platform/{name}")
    fake.repo("platform/old", archived=True)
    fake.repo("platform/empty", default_branch=None)
    fake.repo("platform/dev", default_branch="develop")
    fake.stray.append(fake.repo("elsewhere/shared"))
    fake.repo("x/explicit")

    async with opened(
        fake, scope={"groups": ["platform"], "projects": ["x/explicit"]}
    ) as adapter:
        listing = await adapter.list_projects()

    refs = {p.path: p.ref for p in listing.projects}
    assert listing.complete
    assert refs == {
        "platform/a": "main",
        "platform/b": "main",
        "platform/c": "main",
        "platform/dev": "develop",
        "x/explicit": "main",
    }
    assert fake.calls("groups") == 3


async def test_explicit_branch_is_used_for_every_project() -> None:
    """Ensure an explicit published_ref overrides default branches."""
    fake = FakeGitLab()
    fake.repo("platform/dev", default_branch="develop")

    async with opened(fake, published_ref="release") as adapter:
        listing = await adapter.list_projects()

    assert [p.ref for p in listing.projects] == ["release"]


async def test_missing_group_makes_the_listing_incomplete() -> None:
    """Ensure a 404 group is a problem, not a silently empty scope."""
    fake = FakeGitLab()
    fake.repo("platform/a")

    async with opened(fake, scope={"groups": ["platform", "ghost"]}) as adapter:
        listing = await adapter.list_projects()

    assert not listing.complete
    assert [p.path for p in listing.projects] == ["platform/a"]
    assert "group ghost" in listing.problems[0]


async def test_rejected_token_raises_access_error() -> None:
    """Ensure HTTP 401 fails the listing without echoing the token."""
    fake = FakeGitLab()
    fake.repo("platform/a")
    binding = validate_settings(
        settings(), {"GL_TOKEN": "wrong-token"}, transport=fake.transport()
    )

    async with binding.open_adapter() as adapter:
        with pytest.raises(SourceAccessError, match="GL_TOKEN") as caught:
            await adapter.list_projects()

    assert "wrong-token" not in caught.value.message


async def test_tree_is_paginated_and_filtered() -> None:
    """Ensure keyset tree pages are followed and non-ADR files skipped."""
    fake = FakeGitLab(page_size=2)
    repo = fake.repo("platform/a")
    for day in range(1, 5):
        repo.put(f"doc/decisions/2024-01-0{day}-x.md", adr(str(day)))
    repo.put("doc/decisions/README.md", "# index")

    async with opened(fake) as adapter:
        listing = await adapter.list_documents(project(fake, "platform/a"), {})

    assert listing.complete
    assert len(listing.documents) == 4
    assert all(d.changed for d in listing.documents)
    assert fake.calls("tree") == 3


async def test_unchanged_head_skips_the_tree() -> None:
    """Ensure an unchanged branch head reports all documents unchanged."""
    fake = FakeGitLab()
    repo = fake.repo("platform/a")
    repo.put(ADR, adr("A"))
    repo.put(ADR_B, adr("B"))

    async with opened(fake) as adapter:
        target = project(fake, "platform/a")
        first = await adapter.list_documents(target, {})
        stored = {d.path: d.change_token for d in first.documents}
        second = await adapter.list_documents(target, stored)

    assert fake.calls("tree") == 1
    assert fake.calls("branch") == 2
    assert {d.path: d.change_token for d in second.documents} == stored
    assert not any(d.changed for d in second.documents)


async def test_moved_head_flags_only_changed_blobs() -> None:
    """Ensure a new head relists the tree but flags only new blob ids."""
    fake = FakeGitLab()
    repo = fake.repo("platform/a")
    repo.put(ADR, adr("A"))
    repo.put(ADR_B, adr("B"))

    async with opened(fake) as adapter:
        target = project(fake, "platform/a")
        first = await adapter.list_documents(target, {})
        stored = {d.path: d.change_token for d in first.documents}
        repo.put(ADR_B, adr("B2"))
        second = await adapter.list_documents(target, stored)

    changed = {d.path: d.changed for d in second.documents}
    assert changed == {ADR: False, ADR_B: True}
    assert fake.calls("tree") == 2
    tokens = {d.path: d.change_token for d in second.documents}
    blob, _head, _count, tag = (stored[ADR] or "").split(":")
    assert tokens[ADR] == f"{blob}:{repo.head}:2:{tag}"
    assert tokens[ADR] != stored[ADR]


async def test_missing_count_forces_a_tree_listing() -> None:
    """Ensure a stored set smaller than the listing is not trusted."""
    fake = FakeGitLab()
    repo = fake.repo("platform/a")
    repo.put(ADR, adr("A"))
    repo.put(ADR_B, adr("B"))

    async with opened(fake) as adapter:
        target = project(fake, "platform/a")
        first = await adapter.list_documents(target, {})
        partial = {first.documents[0].path: first.documents[0].change_token}
        second = await adapter.list_documents(target, partial)

    assert fake.calls("tree") == 2
    assert sum(d.changed for d in second.documents) == 1


async def test_missing_adr_path_is_empty_and_complete() -> None:
    """Ensure a tree 404 (no ADR directory) is an empty listing."""
    fake = FakeGitLab()
    fake.repo("platform/a").put("README.md", "x")

    async with opened(fake) as adapter:
        listing = await adapter.list_documents(project(fake, "platform/a"), {})

    assert listing.complete
    assert listing.documents == ()


async def test_missing_branch_raises_not_found() -> None:
    """Ensure a missing published branch fails that project's listing."""
    fake = FakeGitLab()
    fake.repo("platform/a")
    gone = SourceProject(
        id=str(fake.repos["platform/a"].id), path="platform/a", ref="gone"
    )

    async with opened(fake) as adapter:
        with pytest.raises(SourceNotFoundError, match="'gone'"):
            await adapter.list_documents(gone, {})


async def test_fetch_reads_the_raw_blob_and_builds_the_web_url() -> None:
    """Ensure fetch returns exact bytes, a file web URL and no author."""
    fake = FakeGitLab()
    repo = fake.repo("platform/a")
    text = adr("A")
    repo.put(ADR, text)

    async with opened(fake) as adapter:
        await adapter.list_projects()
        listing = await adapter.list_documents(project(fake, "platform/a"), {})
        fetched = await adapter.fetch(listing.documents[0])

    assert fetched.content == text.encode()
    assert fetched.source_url == f"{BASE_URL}/platform/a/-/blob/main/{ADR}"
    assert fetched.author is None


async def test_server_errors_are_retried_with_backoff() -> None:
    """Ensure 5xx answers are retried with exponential backoff."""
    fake = FakeGitLab()
    fake.repo("platform/a").put(ADR, adr("A"))
    fake.script["tree"] = [502, 503]
    sleeps = Sleeps()

    async with opened(fake, sleeps) as adapter:
        listing = await adapter.list_documents(project(fake, "platform/a"), {})

    assert len(listing.documents) == 1
    assert sleeps.waits == [0.5, 1.0]
    assert fake.calls("tree") == 3


async def test_rate_limit_honours_retry_after() -> None:
    """Ensure HTTP 429 waits for the server's Retry-After."""
    fake = FakeGitLab(retry_after="7")
    fake.repo("platform/a")
    fake.script["groups"] = [429]
    sleeps = Sleeps()

    async with opened(fake, sleeps) as adapter:
        listing = await adapter.list_projects()

    assert listing.complete
    assert sleeps.waits == [7.0]


async def test_persistent_failure_gives_up_after_max_attempts() -> None:
    """Ensure retries are capped and end in SourceUnavailableError."""
    fake = FakeGitLab()
    fake.repo("platform/a")
    fake.down.add("branch")
    sleeps = Sleeps()

    async with opened(fake, sleeps) as adapter:
        with pytest.raises(SourceUnavailableError, match="4 attempts"):
            await adapter.list_documents(project(fake, "platform/a"), {})

    assert fake.calls("branch") == gitlab_api.MAX_ATTEMPTS
    assert sleeps.waits == [0.5, 1.0, 2.0]


async def test_transport_errors_are_retried() -> None:
    """Ensure connection errors are retried like 5xx answers."""
    fake = FakeGitLab()
    fake.repo("platform/a")
    failures = [httpx.ConnectError("boom")]

    def handler(request: httpx.Request) -> httpx.Response:
        if failures:
            raise failures.pop()
        return fake.handle(request)

    binding = validate_settings(
        settings(),
        ENV,
        transport=httpx.MockTransport(handler),
        sleep=Sleeps(),
    )
    async with binding.open_adapter() as adapter:
        listing = await adapter.list_projects()

    assert [p.path for p in listing.projects] == ["platform/a"]


async def test_next_link_to_another_origin_is_refused() -> None:
    """Ensure the token is never sent to a foreign next-page link."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        link = '<https://evil.test/api/v4/next>; rel="next"'
        return httpx.Response(200, headers={"Link": link}, json=[])

    binding = validate_settings(
        settings(), ENV, transport=httpx.MockTransport(handler)
    )
    async with binding.open_adapter() as adapter:
        listing = await adapter.list_projects()

    assert not listing.complete
    assert "outside" in listing.problems[0]
    assert all(url.startswith(BASE_URL) for url in seen)


async def test_requests_carry_the_token_header_only() -> None:
    """Ensure the token travels in PRIVATE-TOKEN, never in the URL."""
    fake = FakeGitLab()
    fake.repo("platform/a").put(ADR, adr("A"))

    async with opened(fake) as adapter:
        await adapter.list_projects()

    assert fake.requests
    for request in fake.requests:
        assert request.headers["PRIVATE-TOKEN"] == TOKEN
        assert TOKEN not in str(request.url)
