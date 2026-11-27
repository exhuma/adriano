"""
Promotion of an accepted candidate must not look like a duplicate.

Regression for the phase 07 smoke: a candidate pushed on a feature ref
is accepted, the identical file is then published (filesystem poll),
and the published record's detail page reported ``duplicate_uuid``
against its own candidate. Rows of one UUID are revisions of one ADR;
only a second file claiming an indexed UUID is a duplicate, and it is
not indexed at all (it goes to the not-indexed list).
"""

import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.storage.postgres.store import PostgresStoreProvider
from tests.auth_helpers import sign_in
from tests.routers.approval.support import (
    adr_text,
    as_user,
    candidate,
    decide,
    push,
)

ADR = uuid.UUID("7f3b1e52-4c1d-4a8e-9b0f-2d6e8c4a1b01")
LINKER = uuid.UUID("7f3b1e52-4c1d-4a8e-9b0f-2d6e8c4a1b02")
FILE = "doc/decisions/2024-03-01-use-a-catalog.md"
REF = "feature/ui-demo"


def _write(root: Path, text: str, name: str = FILE) -> None:
    """Write an ADR into the polled tree of project ``platform``."""
    path = root / "platform" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _poll(client: TestClient, settings: Settings) -> None:
    """Poll ``central`` as an admin through the operator route."""
    sign_in(client, roles=["admin"])
    assert client.post("/api/v1/sources/central/poll").status_code == 202


def _published(client: TestClient) -> list[str]:
    """List the ids of every published record, by path."""
    response = client.get("/api/v1/records", params={"state": "published"})
    items = sorted(response.json()["items"], key=lambda item: item["path"])
    return [item["adr_uuid"] for item in items]


def _detail(
    client: TestClient, record_id: str, ref: str | None = None
) -> dict[str, Any]:
    """Read a record detail (a candidate when *ref* is given)."""
    tail = "" if ref is None else f"/candidates/{ref}"
    response = client.get(f"/api/v1/records/{record_id}{tail}")
    assert response.status_code == 200
    return response.json()


def _codes(detail: dict[str, Any]) -> list[str]:
    """List the issue codes of a detail payload."""
    return [issue["code"] for issue in detail["issues"]]


@pytest.fixture
def promoted(
    client: TestClient, router_settings: Settings, root: Path
) -> dict[str, str]:
    """
    Push and accept a candidate, then publish identical content.

    :param client: Test client.
    :param router_settings: Its settings.
    :param root: Polled filesystem root.
    :returns: ``{"candidate": id, "published": id, "digest": digest}``.
    """
    pushed = push(client, candidate(ADR, path=FILE, ref=REF)).json()
    as_user(client)
    assert decide(client, pushed["adr_uuid"]).status_code == 201
    _write(root, adr_text(ADR))
    _poll(client, router_settings)
    (published_id,) = _published(client)
    return {
        "candidate": pushed["adr_uuid"],
        "published": published_id,
        "digest": pushed["digest"],
    }


def test_promoted_record_has_no_duplicate_uuid(
    client: TestClient, promoted: dict[str, str]
) -> None:
    """Ensure the published row is not a duplicate of its own candidate."""
    published = _detail(client, promoted["published"])
    candidate_detail = _detail(client, promoted["candidate"], REF)

    assert "duplicate_uuid" not in _codes(published)
    assert "duplicate_uuid" not in _codes(candidate_detail)
    assert published["metadata"]["digest"] == promoted["digest"]
    approval = published["approval"]
    assert approval["state"] == "accepted"
    assert approval["approvable"] is True
    assert approval["approval_blocker"] is None
    assert approval["divergence"] is None
    assert candidate_detail["approval"]["divergence"] is None
    assert [s["adr_uuid"] for s in published["siblings"]] == [
        promoted["candidate"]
    ]


def test_competing_candidate_is_not_a_duplicate(
    client: TestClient,
    router_settings: Settings,
    promoted: dict[str, str],
) -> None:
    """Ensure a differing candidate competes without ``duplicate_uuid``."""
    other = push(
        client,
        candidate(
            ADR,
            path=FILE,
            ref="feature/other",
            content=adr_text(ADR, body="We use a catalog and a queue."),
        ),
    ).json()
    as_user(client)

    published = _detail(client, promoted["published"])
    competing = _detail(client, other["adr_uuid"], "feature/other")

    assert "duplicate_uuid" not in _codes(published)
    assert "duplicate_uuid" not in _codes(competing)
    assert [
        (c["adr_uuid"], c["ref"])
        for c in published["approval"]["competing_candidates"]
    ] == [(other["adr_uuid"], "feature/other")]
    assert published["approval"]["divergence"] is None
    assert competing["approval"]["state"] == "changed_since_acceptance"
    assert competing["approval"]["approvable"] is True
    assert competing["approval"]["can_decide"] is True
    assert competing["approval"]["divergence"]["kind"] == "published_differs"


def test_divergent_published_content_stays_decidable(
    client: TestClient, router_settings: Settings, root: Path
) -> None:
    """Ensure a published row with an accepted candidate can be decided."""
    pushed = push(client, candidate(ADR, path=FILE, ref=REF)).json()
    as_user(client)
    assert decide(client, pushed["adr_uuid"]).status_code == 201
    _write(root, adr_text(ADR, body="Published differently."))
    _poll(client, router_settings)
    (published_id,) = _published(client)
    as_user(client)

    detail = _detail(client, published_id)

    assert "duplicate_uuid" not in _codes(detail)
    approval = detail["approval"]
    assert approval["state"] == "changed_since_acceptance"
    assert approval["approvable"] is True
    assert approval["can_decide"] is True
    assert approval["divergence"]["kind"] == "published_not_accepted"
    assert decide(client, published_id).status_code == 201


def test_link_to_promoted_record_resolves_once(
    client: TestClient,
    router_settings: Settings,
    root: Path,
    promoted: dict[str, str],
) -> None:
    """Ensure a link to an ADR with a candidate resolves once."""
    linker = adr_text(LINKER, title="Replace the catalog").replace(
        "decision-date:", f"obsoletes: [{ADR}]\ndecision-date:"
    )
    _write(root, linker, "doc/decisions/2024-04-01-replace.md")
    _poll(client, router_settings)
    published = _detail(client, promoted["published"])

    inbound = published["inbound_links"]

    assert [link["source_title"] for link in inbound] == ["Replace the catalog"]
    assert published["status"] == "obsoleted"
    assert _codes(published) == []


def test_second_file_with_an_indexed_uuid_is_not_indexed(
    client: TestClient,
    router_settings: Settings,
    root: Path,
    provider: PostgresStoreProvider,
) -> None:
    """Ensure the first file (by path) holds a UUID, the copy is queued."""
    _write(root, adr_text(ADR))
    _write(root, adr_text(ADR), "doc/decisions/2024-03-02-copy.md")
    _poll(client, router_settings)

    [held] = _published(client)
    with provider.unit_of_work() as store:
        [entry] = store.list_not_indexed()

    detail = _detail(client, held)
    assert detail["provenance"]["path"] == FILE
    assert "duplicate_uuid" not in _codes(detail)
    assert entry.key.path == "doc/decisions/2024-03-02-copy.md"
    assert entry.holder_uuid == ADR
    assert [r.code.value for r in entry.reasons] == ["duplicate_uuid"]
    assert FILE in entry.reasons[0].message
