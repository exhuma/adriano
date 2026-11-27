"""
Tests for the push holder rule and the push side of the not-indexed list.

A push is accepted for an unheld UUID or one whose published holder is
in the same registration and project; anything else is refused with
409 ``duplicate_uuid``. Refused pushes that concern a document are
listed as not indexed (origin ``push``) and cleared by a later
successful push for the same location, never by a poll not listing
them.
"""

import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.storage.port import RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.auth_helpers import sign_in
from tests.routers.approval.support import (
    OTHER_TOKEN,
    adr_text,
    candidate,
    push,
)
from tests.routers.conftest import adr, seed

ADR = uuid.UUID("9c1d2e3f-0000-4a4a-9a9a-000000000001")
HELD_PATH = "doc/decisions/2024-03-01-held.md"
PUSHED_PATH = "doc/decisions/2024-03-02-pushed.md"
REF = "feature/catalog"


def _entries(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    """List not-indexed entries as an admin."""
    sign_in(client, roles=["admin"])
    response = client.get("/api/v1/not-indexed", params=params)
    assert response.status_code == 200
    return response.json()["items"]


def _entry(client: TestClient, item: dict[str, Any]) -> dict[str, Any]:
    """Read the detail of a listed entry."""
    keys = ("source_id", "project", "path", "ref")
    response = client.get(
        "/api/v1/not-indexed/entry", params={k: item[k] for k in keys}
    )
    assert response.status_code == 200
    return response.json()


def _hold(provider: PostgresStoreProvider, **where: str) -> None:
    """Publish ``ADR`` at a location."""
    with provider.lock_registration(where.get("source_id", "central")) as s:
        seed(s, path=HELD_PATH, content=adr(ADR, title="Held"), **where)


def test_a_uuid_held_in_another_project_is_refused_and_queued(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure the duplicate gets 409, a queue entry and its content."""
    _hold(provider, project="platform")

    response = push(
        client,
        candidate(ADR, project="payments", path=PUSHED_PATH, ref=REF),
    )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "duplicate_uuid"
    assert str(ADR) in body["detail"]
    assert HELD_PATH not in body["detail"]
    [item] = _entries(client)
    assert item["origin"] == "push"
    assert item["holder_uuid"] == str(ADR)
    assert [r["code"] for r in item["reasons"]] == ["duplicate_uuid"]
    assert (item["source_id"], item["project"]) == ("central", "payments")
    assert (item["path"], item["ref"]) == (PUSHED_PATH, REF)
    assert str(ADR) in (_entry(client, item)["content"] or "")


def test_a_uuid_held_by_another_source_is_refused(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure holders in other registrations block a push as well."""
    _hold(provider, project="platform")

    response = push(
        client,
        candidate(ADR, source_id="other", path=PUSHED_PATH),
        token=OTHER_TOKEN,
    )

    assert response.status_code == 409
    assert _entries(client, source_id="other")[0]["origin"] == "push"


def test_the_holders_own_project_may_push_any_ref_and_path(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure same source and project is accepted, and queues nothing."""
    _hold(provider, project="platform")

    response = push(client, candidate(ADR, path=PUSHED_PATH, ref=REF))

    assert response.status_code == 201
    assert _entries(client) == []
    detail = client.get(f"/api/v1/records/{ADR}").json()
    assert detail["metadata"]["kind"] == "published"
    assert [s["ref"] for s in detail["siblings"]] == [REF]


def test_an_unheld_uuid_is_accepted_from_any_project(
    client: TestClient,
) -> None:
    """Ensure candidate-only ADRs do not hold a UUID against a push."""
    first = push(client, candidate(ADR, project="platform", ref="feature/a"))
    second = push(client, candidate(ADR, project="payments", ref="feature/b"))

    assert (first.status_code, second.status_code) == (201, 201)
    assert _entries(client) == []


def test_invalid_and_mismatched_documents_are_queued(
    client: TestClient,
) -> None:
    """Ensure refused documents keep their reasons and their content."""
    other = uuid.uuid4()
    bad = push(
        client, candidate(ADR, content="no frontmatter here", path="bad.md")
    )
    mismatch = push(
        client,
        candidate(ADR, content=adr_text(other), path="mismatch.md"),
    )

    assert bad.status_code == mismatch.status_code == 422
    by_path = {e["path"]: e for e in _entries(client)}
    assert [r["code"] for r in by_path["bad.md"]["reasons"]] == [
        "missing_frontmatter"
    ]
    assert [r["code"] for r in by_path["mismatch.md"]["reasons"]] == [
        "uuid_mismatch"
    ]
    assert all(e["origin"] == "push" for e in by_path.values())
    assert _entry(client, by_path["bad.md"])["content"] == (
        "no frontmatter here"
    )
    assert str(other) in (_entry(client, by_path["mismatch.md"])["content"])


def test_the_published_ref_is_queued_with_its_content(
    client: TestClient,
) -> None:
    """Ensure a push to the published ref is listed, with content."""
    response = push(client, candidate(ADR, ref="local", path="main.md"))

    assert response.status_code == 422
    assert response.json()["code"] == "published_ref_not_allowed"
    [item] = _entries(client)
    assert item["reasons"][0]["code"] == "published_ref_not_allowed"
    assert item["has_content"] is True


def test_oversized_content_is_queued_without_content(
    client: TestClient,
) -> None:
    """Ensure content over the limit is listed but not stored."""
    big = adr_text(ADR, body="x" * (1024 * 1024))

    response = push(client, candidate(ADR, content=big, path="big.md"))

    assert response.status_code == 413
    [item] = _entries(client)
    assert item["reasons"][0]["code"] == "content_too_large"
    assert item["has_content"] is False


def test_a_default_path_names_the_location(client: TestClient) -> None:
    """Ensure a push without a path is keyed by its synthesised path."""
    push(client, candidate(ADR, content="nope", path=None))

    [item] = _entries(client)

    assert item["path"].endswith(f"{ADR}.md")


def test_requests_that_say_nothing_about_a_document_are_not_queued(
    client: TestClient,
) -> None:
    """Ensure auth, scope and create-only refusals queue nothing."""
    assert push(client, candidate(ADR), token="wrong").status_code == 401
    assert push(client, candidate(ADR, project="elsewhere")).status_code == 403
    assert push(client, candidate(ADR)).status_code == 201
    assert push(client, candidate(ADR), method="POST").status_code == 409

    assert _entries(client) == []


def test_a_successful_push_clears_its_location(client: TestClient) -> None:
    """Ensure fixing the document and pushing again clears the entry."""
    push(client, candidate(ADR, content="broken", path=PUSHED_PATH, ref=REF))
    push(client, candidate(ADR, content="broken", path="elsewhere.md"))
    assert len(_entries(client)) == 2

    fixed = push(client, candidate(ADR, path=PUSHED_PATH, ref=REF))

    assert fixed.status_code == 201
    assert [e["path"] for e in _entries(client)] == ["elsewhere.md"]


def test_a_repeated_refusal_keeps_one_entry(client: TestClient) -> None:
    """Ensure the same location is listed once, first seen kept."""
    push(client, candidate(ADR, content="broken", path="x.md"))
    first = _entries(client)[0]
    push(client, candidate(ADR, content="still broken", path="x.md"))

    [again] = _entries(client)

    assert again["first_seen_at"] == first["first_seen_at"]
    assert again["last_seen_at"] >= first["last_seen_at"]
    assert _entry(client, again)["content"] == "still broken"


def _write(root: Path, project: str, path: str, text: str) -> None:
    """Write an ADR into the polled tree."""
    target = root / project / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _poll(client: TestClient, router_settings: Settings) -> None:
    """Poll ``central`` through the operator route (runs inline)."""
    sign_in(client, roles=["admin"])
    assert client.post("/api/v1/sources/central/poll").status_code == 202


def test_a_poll_keeps_push_entries_it_does_not_list(
    client: TestClient, router_settings: Settings, root: Path
) -> None:
    """Ensure a poll never clears a push entry for not listing it."""
    push(client, candidate(ADR, content="broken", path="x.md"))
    _write(root, "platform", HELD_PATH, adr_text(uuid.uuid4()))

    _poll(client, router_settings)

    assert [e["path"] for e in _entries(client, origin="push")] == ["x.md"]


def test_a_poll_clears_the_duplicate_it_now_indexes(
    client: TestClient, router_settings: Settings, root: Path
) -> None:
    """Ensure indexing the claimed UUID at that location clears the entry."""
    _write(root, "platform", HELD_PATH, adr_text(ADR))
    _poll(client, router_settings)
    refused = push(
        client,
        candidate(ADR, project="payments", path=PUSHED_PATH, ref=REF),
    )
    assert refused.status_code == 409
    assert len(_entries(client, origin="push")) == 1

    (root / "platform" / HELD_PATH).unlink()
    _write(root, "payments", PUSHED_PATH, adr_text(ADR))
    _poll(client, router_settings)

    assert _entries(client, origin="push") == []
    record = client.get(f"/api/v1/records/{ADR}").json()
    assert record["provenance"]["project"] == "payments"
    assert record["metadata"]["kind"] == RecordState.PUBLISHED.value
