"""
The governance loop end to end: push -> accept -> publish -> edit.

A candidate is pushed and accepted; the identical file (with CRLF line
endings and a BOM) is then written into the polled filesystem tree and
polled through the operator route; later the file is edited and polled
again. Covers criteria 13, 16-20; diff behaviour per the approval domain docs.
"""

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from tests.auth_helpers import sign_in
from tests.routers.approval.support import (
    ClientFactory,
    adr_text,
    as_user,
    candidate,
    decide,
    push,
)

ADR = uuid.UUID("5d2a7c61-0c4e-4f43-9a61-3c1d1f1e0a01")
FILE = "doc/decisions/2024-03-01-use-a-catalog.md"
REQUIRED_FALSE = """
approval_policy:
  id: global
  version: 4
  required: false
"""


def _admin(client: TestClient, settings: Settings) -> None:
    """Switch the client back to an admin (read + operate)."""
    sign_in(client, roles=["admin"])


def _poll(client: TestClient, settings: Settings) -> None:
    """Poll ``central`` through the operator route (runs inline)."""
    _admin(client, settings)
    response = client.post("/api/v1/sources/central/poll")
    assert response.status_code == 202
    source = next(
        s for s in client.get("/api/v1/sources").json() if s["id"] == "central"
    )
    assert source["last_status"] == "ok"


def _published_id(client: TestClient) -> str:
    """Find the single published record."""
    items = client.get("/api/v1/records", params={"state": "published"}).json()[
        "items"
    ]
    assert len(items) == 1
    return items[0]["id"]


def _detail(client: TestClient, record_id: str) -> dict[str, object]:
    """Read a record detail."""
    response = client.get(f"/api/v1/records/{record_id}")
    assert response.status_code == 200
    return response.json()


def _approval(client: TestClient, record_id: str) -> dict[str, object]:
    """Read the approval block of a record."""
    approval = _detail(client, record_id)["approval"]
    assert isinstance(approval, dict)
    return approval


def _write(root: Path, text: str) -> None:
    """Write the ADR into the polled tree with CRLF and a BOM."""
    path = root / "platform" / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode())


@pytest.fixture
def accepted(client: TestClient, router_settings: Settings) -> dict[str, str]:
    """
    Push a candidate and accept it as a reviewer.

    :param client: Test client.
    :param router_settings: Its settings.
    :returns: The intake response body.
    """
    pushed = push(client, candidate(ADR, path=FILE)).json()
    as_user(client)
    assert decide(client, pushed["record_id"]).status_code == 201
    return pushed


def test_identical_content_is_accepted_when_published(
    client: TestClient,
    router_settings: Settings,
    root: Path,
    accepted: dict[str, str],
) -> None:
    """Ensure promotion keeps the digest and the acceptance history."""
    _write(root, adr_text(ADR))

    _poll(client, router_settings)
    published_id = _published_id(client)
    detail = _detail(client, published_id)
    approval = _approval(client, published_id)

    metadata = detail["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["kind"] == "published"
    assert metadata["digest"] == accepted["digest"]
    assert approval["state"] == "accepted"
    history = approval["history"]
    assert isinstance(history, list) and len(history) == 1
    assert history[0]["current_digest"] is True
    assert history[0]["provenance"]["kind"] == "candidate"
    assert approval["divergence"] is None
    candidate_state = _approval(client, accepted["record_id"])["state"]
    assert candidate_state == "accepted"
    diff = client.get(f"/api/v1/records/{published_id}/diff").json()
    assert diff["base"] is None
    assert diff["reason"] == "no_prior_revision"


def test_edited_content_needs_new_approval_and_diffs(
    client: TestClient,
    router_settings: Settings,
    root: Path,
    accepted: dict[str, str],
) -> None:
    """Ensure an edit changes the digest and keeps the old history."""
    _write(root, adr_text(ADR))
    _poll(client, router_settings)
    published_id = _published_id(client)
    _write(root, adr_text(ADR, body="We use a catalog and a review."))

    _poll(client, router_settings)
    approval = _approval(client, published_id)
    diff = client.get(f"/api/v1/records/{published_id}/diff")

    assert approval["state"] == "changed_since_acceptance"
    assert approval["needs_approval"] is True
    assert approval["digest"] != accepted["digest"]
    assert approval["last_accepted_digest"] == accepted["digest"]
    history = approval["history"]
    assert isinstance(history, list) and len(history) == 1
    assert history[0]["current_digest"] is False
    divergence = approval["divergence"]
    assert isinstance(divergence, dict)
    assert divergence["kind"] == "published_not_accepted"
    assert divergence["other_record_ids"] == [accepted["record_id"]]
    candidate_view = _approval(client, accepted["record_id"])
    assert candidate_view["state"] == "accepted"
    candidate_divergence = candidate_view["divergence"]
    assert isinstance(candidate_divergence, dict)
    assert candidate_divergence["kind"] == "published_differs"
    assert diff.status_code == 200
    body = diff.json()
    assert body["base"]["digest"] == accepted["digest"]
    assert body["base"]["label"] == "last accepted"
    assert body["base"]["decided_at"]
    assert body["target"]["label"] == "current revision"
    assert body["identical"] is False
    assert "-We use a catalog." in body["unified_diff"]
    assert "+We use a catalog and a review." in body["unified_diff"]
    assert (body["lines_added"], body["lines_removed"]) == (1, 1)
    assert accepted["digest"][len("sha256-v1:") :][:12] in body["unified_diff"]


def test_diff_refuses_unrelated_digests(
    client: TestClient, accepted: dict[str, str]
) -> None:
    """Ensure the diff endpoint is not an arbitrary snapshot reader."""
    other = push(client, candidate(uuid.uuid4(), ref="feature/b")).json()
    url = f"/api/v1/records/{accepted['record_id']}/diff"

    unrelated = client.get(url, params={"from": other["digest"]})
    unknown = client.get(url, params={"to": "sha256-v1:" + "0" * 64})

    assert unrelated.status_code == 404
    assert unrelated.json()["code"] == "unknown_revision"
    assert unknown.status_code == 404


def test_candidate_diff_uses_previous_revision(client: TestClient) -> None:
    """Ensure an undecided candidate diffs against its previous push."""
    first = push(client, candidate(ADR)).json()
    second = push(
        client, candidate(ADR, content=adr_text(ADR, body="Second."))
    ).json()

    diff = client.get(f"/api/v1/records/{first['record_id']}/diff").json()
    same = client.get(
        f"/api/v1/records/{first['record_id']}/diff",
        params={"from": second["digest"], "to": second["digest"]},
    ).json()

    assert diff["base"]["digest"] == first["digest"]
    assert diff["base"]["label"] == "previous revision"
    assert diff["target"]["digest"] == second["digest"]
    assert same["identical"] is True
    assert same["unified_diff"] == ""


def test_needs_approval_filter_across_states(
    client: TestClient,
    router_settings: Settings,
    make_client: ClientFactory,
    root: Path,
    accepted: dict[str, str],
) -> None:
    """Ensure needs-approval covers every unmet state and no other."""
    _write(root, adr_text(ADR, body="Different published text."))
    _poll(client, router_settings)
    changed = _published_id(client)
    pending = push(client, candidate(uuid.uuid4(), ref="feature/p")).json()
    rejected = push(client, candidate(uuid.uuid4(), ref="feature/r")).json()
    as_user(client)
    assert decide(client, rejected["record_id"], "rejected").status_code == 201

    def needing(test_client: TestClient) -> set[str]:
        response = test_client.get(
            "/api/v1/records", params={"needs_approval": "true"}
        )
        return {item["id"] for item in response.json()["items"]}

    everything = {
        accepted["record_id"],
        changed,
        pending["record_id"],
        rejected["record_id"],
    }
    assert needing(client) == everything - {accepted["record_id"]}
    assert needing(make_client(None)) == everything
    assert needing(make_client(REQUIRED_FALSE)) == set()
