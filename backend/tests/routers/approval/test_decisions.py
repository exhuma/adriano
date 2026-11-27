"""
Tests for accept/reject decisions and the caller's ``can_decide``.

Candidates are pushed through the real intake route, then decided
through ``POST /api/v1/records/{id}/decisions`` (criteria 3, 16, 22).
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.auth.dev import DEV_ISSUER
from app.config import Settings
from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.approval.support import (
    POLICY,
    ClientFactory,
    as_user,
    candidate,
    decide,
    push,
)
from tests.routers.conftest import seed


def _pushed(client: TestClient, **overrides: Any) -> dict[str, str]:
    """
    Push a fresh candidate.

    :param client: Test client.
    :param overrides: Candidate body overrides.
    :returns: The intake response body.
    """
    adr_uuid = uuid.uuid4()
    response = push(client, candidate(adr_uuid, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def _approval(client: TestClient, record_id: str) -> dict[str, object]:
    """Read the approval block of a record's detail."""
    return client.get(f"/api/v1/records/{record_id}").json()["approval"]


def test_reviewer_role_accepts(
    client: TestClient, router_settings: Settings
) -> None:
    """Ensure a reviewer role accepts the exact current digest."""
    pushed = _pushed(client)
    as_user(client)
    assert _approval(client, pushed["record_id"])["can_decide"] is True

    response = decide(
        client,
        pushed["record_id"],
        comment="  Looks right.  ",
        expected_digest=pushed["digest"],
    )

    assert response.status_code == 201
    event = response.json()
    assert event["digest"] == pushed["digest"]
    assert event["action"] == "accepted"
    assert event["actor_issuer"] == DEV_ISSUER
    assert event["actor_subject"] == "rita"
    assert event["comment"] == "Looks right."
    assert (event["policy_id"], event["policy_version"]) == ("global", 3)
    assert event["provenance"]["record_id"] == pushed["record_id"]
    assert event["provenance"]["ref"] == "feature/catalog"
    approval = _approval(client, pushed["record_id"])
    assert approval["state"] == "accepted"
    assert approval["needs_approval"] is False
    assert approval["can_decide"] is False
    assert approval["decide_blocked_code"] == "already_decided"
    history = approval["history"]
    assert isinstance(history, list) and len(history) == 1
    assert history[0]["current_digest"] is True


def test_listed_user_is_eligible(
    client: TestClient, router_settings: Settings
) -> None:
    """Ensure an ``issuer|subject`` reviewer without the role can decide."""
    pushed = _pushed(client)
    as_user(client, sub="carol", roles=("adr-reader",))

    response = decide(client, pushed["record_id"], "rejected")

    assert response.status_code == 201
    assert _approval(client, pushed["record_id"])["state"] == "rejected"


def test_reader_is_not_eligible(
    client: TestClient, router_settings: Settings
) -> None:
    """Ensure read permission alone never allows a decision."""
    pushed = _pushed(client)
    as_user(client, sub="rob", roles=("adr-reader",))

    response = decide(client, pushed["record_id"])
    approval = _approval(client, pushed["record_id"])

    assert response.status_code == 403
    assert response.json()["code"] == "not_eligible"
    assert "reviewers" in response.json()["hint"]
    assert approval["can_decide"] is False
    assert approval["decide_blocked_code"] == "not_eligible"


def test_missing_policy_refuses_decisions(
    client: TestClient, make_client: ClientFactory, router_settings: Settings
) -> None:
    """Ensure decisions are refused (409) while the policy is missing."""
    pushed = _pushed(client)
    no_policy = make_client(None)
    as_user(no_policy)

    response = decide(no_policy, pushed["record_id"])

    assert response.status_code == 409
    assert response.json()["code"] == "policy_missing"
    assert "approval_policy" in response.json()["hint"]
    approval = _approval(no_policy, pushed["record_id"])
    assert approval["state"] == "policy_missing"
    assert approval["decide_blocked_code"] == "policy_missing"


def test_self_approval_is_refused(
    client: TestClient, router_settings: Settings
) -> None:
    """Ensure the author (by verified email) cannot decide (403)."""
    pushed = _pushed(client, author="Rita@Example.com")
    as_user(client, email="rita@example.com")

    response = decide(client, pushed["record_id"])

    assert response.status_code == 403
    assert response.json()["code"] == "self_approval"
    blocked = _approval(client, pushed["record_id"])["decide_blocked_code"]
    assert blocked == "self_approval"


def test_self_approval_by_principal_is_refused(
    client: TestClient, router_settings: Settings
) -> None:
    """Ensure an ``issuer|subject`` author is also recognised."""
    pushed = _pushed(client, author=f"{DEV_ISSUER}|rita")
    as_user(client, email=None)

    response = decide(client, pushed["record_id"])

    assert response.status_code == 403
    assert response.json()["code"] == "self_approval"


def test_deciding_twice_is_409(
    client: TestClient, router_settings: Settings
) -> None:
    """Ensure one formal decision per (identity, digest)."""
    pushed = _pushed(client)
    as_user(client)
    assert decide(client, pushed["record_id"]).status_code == 201
    as_user(client, sub="carol", roles=("adr-reader",))

    response = decide(client, pushed["record_id"], "rejected")

    assert response.status_code == 409
    assert response.json()["code"] == "already_decided"


def test_expected_digest_mismatch_is_409(
    client: TestClient, router_settings: Settings
) -> None:
    """Ensure a reviewer never decides content they did not see."""
    pushed = _pushed(client)
    as_user(client)

    response = decide(
        client, pushed["record_id"], expected_digest="sha256-v1:" + "0" * 64
    )

    assert response.status_code == 409
    assert response.json()["code"] == "digest_changed"


def test_rejection_needs_approval(
    client: TestClient, router_settings: Settings
) -> None:
    """Ensure a rejected record appears in the needs-approval filter."""
    pushed = _pushed(client)
    as_user(client)

    assert decide(client, pushed["record_id"], "rejected").status_code == 201
    listed = client.get("/api/v1/records", params={"needs_approval": "true"})

    ids = {item["id"]: item for item in listed.json()["items"]}
    assert ids[pushed["record_id"]]["approval_state"] == "rejected"


def test_unknown_record_is_404(
    client: TestClient, router_settings: Settings
) -> None:
    """Ensure deciding an unknown record answers 404."""
    as_user(client)

    response = decide(client, str(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["code"] == "record_not_found"


def test_comment_length_and_extra_fields_are_validated(
    client: TestClient, router_settings: Settings
) -> None:
    """Ensure overlong comments and unknown fields answer 422."""
    pushed = _pushed(client)
    as_user(client)

    long_comment = decide(client, pushed["record_id"], comment="x" * 2001)
    extra = decide(client, pushed["record_id"], digest="sha256-v1:00")

    assert long_comment.status_code == 422
    assert extra.status_code == 422


def test_decisions_need_authentication(client: TestClient) -> None:
    """Ensure a push token cannot record decisions."""
    pushed = _pushed(client)
    client.cookies.clear()

    response = client.post(
        f"/api/v1/records/{pushed['record_id']}/decisions",
        json={"action": "accepted"},
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401


def test_history_survives_a_new_app_and_is_append_only(
    client: TestClient,
    make_client: ClientFactory,
    router_settings: Settings,
    clean_engine: Engine,
) -> None:
    """Ensure decisions persist across app instances and are immutable."""
    pushed = _pushed(client)
    as_user(client)
    event = decide(client, pushed["record_id"]).json()

    restarted = make_client(POLICY)
    history = _approval(restarted, pushed["record_id"])["history"]

    assert isinstance(history, list)
    assert [h["id"] for h in history] == [event["id"]]
    for statement in (
        "UPDATE decision_event SET comment = 'tampered'",
        "DELETE FROM decision_event",
    ):
        with pytest.raises(DBAPIError):
            with clean_engine.begin() as connection:
                connection.execute(text(statement))


def test_unapprovable_records_cannot_be_decided(
    client: TestClient,
    router_settings: Settings,
    provider: PostgresStoreProvider,
) -> None:
    """Ensure a record without a valid UUID answers 409."""
    with provider.lock_registration("central") as store:
        record_id = seed(store, content=b"---\ntitle: x\n---\nBody\n")
    as_user(client)

    response = decide(client, str(record_id))

    assert response.status_code == 409
    assert response.json()["code"] == "not_approvable"
    approval = _approval(client, str(record_id))
    assert approval["approvable"] is False
    assert approval["decide_blocked_code"] == "not_approvable"
