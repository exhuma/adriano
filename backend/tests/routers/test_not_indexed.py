"""Tests for ``GET /api/v1/not-indexed`` and its entry detail route."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.issues import IssueCode, error
from app.services.ingest import (
    IncomingDocument,
    not_indexed_entry,
    prepare_document,
    queue_document,
)
from app.storage.port import (
    IntakeKind,
    NotIndexedKey,
    NotIndexedWrite,
)
from app.storage.postgres.store import PostgresStoreProvider
from tests.auth_helpers import sign_in
from tests.routers.conftest import adr, seed

HOLDER = uuid.UUID("5b0c2f4e-1a2b-4c3d-8e9f-001122334455")


def _queue(
    provider: PostgresStoreProvider,
    *,
    source_id: str = "central",
    project: str = "platform",
    path: str = "doc/decisions/2024-01-02-broken.md",
    ref: str = "local",
    content: bytes = b"not frontmatter at all",
    origin: IntakeKind = IntakeKind.POLL,
    holder: uuid.UUID | None = None,
) -> None:
    """Queue one rejected document."""
    prepared = prepare_document(
        IncomingDocument(
            source_id=source_id,
            project=project,
            path=path,
            ref=ref,
            content=content,
            source_url=f"https://example.org/{path}",
        )
    )
    reasons = (
        (error(IssueCode.DUPLICATE_UUID, f"UUID {holder} is held"),)
        if holder
        else None
    )
    with provider.lock_registration(source_id) as store:
        queue_document(
            store,
            prepared,
            not_indexed_entry(
                prepared, origin, reasons=reasons, holder_uuid=holder
            ),
        )


def _list(client: TestClient, **params: Any) -> dict[str, Any]:
    """Read the list."""
    response = client.get("/api/v1/not-indexed", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_list_describes_each_entry(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure items carry location, origin, reasons, holder and times."""
    _queue(provider, holder=HOLDER, content=adr(HOLDER))

    [item] = _list(client)["items"]

    assert (item["source_id"], item["project"], item["ref"]) == (
        "central",
        "platform",
        "local",
    )
    assert item["path"] == "doc/decisions/2024-01-02-broken.md"
    assert item["origin"] == "poll"
    assert item["holder_uuid"] == str(HOLDER)
    assert item["reasons"][0]["code"] == "duplicate_uuid"
    assert "message" in item["reasons"][0]
    assert item["source_url"].startswith("https://example.org/")
    assert item["has_content"] is True
    assert item["first_seen_at"] <= item["last_seen_at"]


def test_the_list_is_newest_first_and_paginated(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure last_seen_at orders the list and pages are bounded."""
    for n in range(3):
        _queue(provider, path=f"doc/decisions/{n}.md")
    _queue(provider, path="doc/decisions/0.md")  # seen again: now newest

    first = _list(client, page_size=2)
    second = _list(client, page_size=2, page=2)

    assert first["total"] == 3
    assert [i["path"] for i in first["items"]] == [
        "doc/decisions/0.md",
        "doc/decisions/2.md",
    ]
    assert [i["path"] for i in second["items"]] == ["doc/decisions/1.md"]
    assert (
        client.get(
            "/api/v1/not-indexed", params={"page_size": 1000}
        ).status_code
        == 422
    )


def test_the_list_filters(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure source, project, reason and origin narrow the list."""
    _queue(provider, path="a.md")
    _queue(provider, source_id="other", path="b.md", origin=IntakeKind.PUSH)
    _queue(provider, project="payments", path="c.md", holder=HOLDER)

    def paths(**params: str) -> set[str]:
        return {i["path"] for i in _list(client, **params)["items"]}

    assert paths(source_id="other") == {"b.md"}
    assert paths(project="payments") == {"c.md"}
    assert paths(origin="push") == {"b.md"}
    assert paths(reason="duplicate_uuid") == {"c.md"}
    assert paths(reason="missing_frontmatter") == {"a.md", "b.md"}
    assert paths(source_id="central", origin="poll", project="platform") == {
        "a.md"
    }
    assert (
        client.get("/api/v1/not-indexed", params={"reason": "nope"}).status_code
        == 422
    )


def test_the_entry_route_returns_the_rejected_content(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure a location with slashes in project, path and ref resolves."""
    _queue(
        provider,
        project="group/sub/repo",
        path="doc/decisions/x.md",
        ref="feature/deep",
        content=b"first line\nsecond line\n",
    )

    response = client.get(
        "/api/v1/not-indexed/entry",
        params={
            "source_id": "central",
            "project": "group/sub/repo",
            "path": "doc/decisions/x.md",
            "ref": "feature/deep",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "second line" in body["content"]
    assert body["reasons"][0]["code"] == "missing_frontmatter"
    assert body["ref"] == "feature/deep"


def test_an_entry_without_content_and_an_unknown_one(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure unread documents have no content and unknown ones are 404."""
    with provider.lock_registration("central") as store:
        store.put_not_indexed(
            NotIndexedWrite(
                key=NotIndexedKey("central", "platform", "gone.md", "local"),
                origin=IntakeKind.POLL,
                reasons=(error(IssueCode.FETCH_FAILED, "unreadable"),),
            )
        )
    location = {
        "source_id": "central",
        "project": "platform",
        "path": "gone.md",
        "ref": "local",
    }

    [item] = _list(client)["items"]
    found = client.get("/api/v1/not-indexed/entry", params=location)
    missing = client.get(
        "/api/v1/not-indexed/entry", params={**location, "path": "no.md"}
    )

    assert item["has_content"] is False
    assert found.json()["content"] is None
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_indexed_not_found"
    assert (
        client.get(
            "/api/v1/not-indexed/entry", params={"source_id": "central"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "path", ["/api/v1/not-indexed", "/api/v1/not-indexed/entry"]
)
def test_access_follows_the_read_permission(
    client: TestClient, path: str
) -> None:
    """Ensure every signed-in reader sees it; others do not."""
    params = {
        "source_id": "central",
        "project": "p",
        "path": "x.md",
        "ref": "r",
    }
    sign_in(client, roles=["adr-reader"])
    reader = client.get(path, params=params)
    sign_in(client, roles=["poller"])
    forbidden = client.get(path, params=params)
    client.cookies.clear()
    anonymous = client.get(path, params=params)

    assert reader.status_code in (200, 404)
    assert forbidden.status_code == 403
    assert anonymous.status_code == 401


def test_sources_count_their_not_indexed_entries(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure GET /sources reports the queue size per registration."""
    _queue(provider, path="a.md")
    _queue(provider, path="b.md", origin=IntakeKind.PUSH)
    _queue(provider, source_id="other", path="c.md")
    with provider.lock_registration("central") as store:
        seed(store, content=adr(uuid.uuid4()))

    counts = {
        s["id"]: s["not_indexed_count"]
        for s in client.get("/api/v1/sources").json()
    }

    assert counts == {"central": 2, "other": 1}
