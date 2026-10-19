"""
Tests for CI push intake (``PUT``/``POST /api/v1/candidates``).

Real HTTP through the app against the test database, with push tokens
exported by :func:`tests.routers.approval.support.set_push_tokens`
(criteria 7, 8, 12).
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.config import Settings
from app.sources import filesystem
from app.storage.port import RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.approval.support import (
    CENTRAL_TOKEN,
    OTHER_TOKEN,
    POLLONLY_TOKEN,
    adr_text,
    as_user,
    candidate,
    decide,
    push,
)
from tests.routers.conftest import seed

ADR = uuid.UUID("0b0c2f4e-1111-4a4a-9a9a-000000000001")


def _revision_count(engine: Engine) -> int:
    """Count stored snapshots."""
    with engine.connect() as connection:
        return connection.execute(text("SELECT count(*) FROM revision")).one()[
            0
        ]


def test_put_creates_then_is_idempotent(
    client: TestClient, clean_engine: Engine
) -> None:
    """Ensure PUT creates once and an identical PUT changes nothing."""
    first = push(client, candidate(ADR, author="ann@example.com"))
    revisions = _revision_count(clean_engine)
    second = push(client, candidate(ADR, author="ann@example.com"))

    assert first.status_code == 201
    body = first.json()
    assert body["created"] is True
    assert body["updated"] is False
    assert body["deduplicated"] is False
    assert body["digest"].startswith("sha256-v1:")
    assert body["catalog_path"] == f"/records/{body['record_id']}"
    assert second.status_code == 200
    assert second.json() == {**body, "created": False}
    assert _revision_count(clean_engine) == revisions
    detail = client.get(f"/api/v1/records/{body['record_id']}").json()
    assert detail["metadata"]["kind"] == "candidate"
    assert detail["metadata"]["digest"] == body["digest"]
    assert detail["metadata"]["previous_digest"] is None
    assert detail["provenance"]["ref"] == "feature/catalog"
    assert detail["provenance"]["path"].endswith("2024-03-01-use-a-catalog.md")


def test_put_replace_updates_digest_and_keeps_previous(
    client: TestClient,
) -> None:
    """Ensure PUT with changed content replaces the candidate in place."""
    first = push(client, candidate(ADR)).json()

    changed = push(client, candidate(ADR, content=adr_text(ADR, body="New.")))

    assert changed.status_code == 200
    assert changed.json()["updated"] is True
    assert changed.json()["record_id"] == first["record_id"]
    assert changed.json()["digest"] != first["digest"]
    detail = client.get(f"/api/v1/records/{first['record_id']}").json()
    assert detail["metadata"]["previous_digest"] == first["digest"]


def test_client_digest_is_refused(client: TestClient) -> None:
    """Ensure a client-supplied digest is an unexpected field (422)."""
    response = push(client, candidate(ADR, digest="sha256-v1:" + "0" * 64))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert response.json()["errors"][0]["loc"] == ["digest"]


def test_post_conflicts_when_candidate_exists(client: TestClient) -> None:
    """Ensure POST creates once and answers 409 afterwards."""
    created = push(client, candidate(ADR), method="POST")
    again = push(client, candidate(ADR), method="POST")
    other_ref = push(client, candidate(ADR, ref="feature/b"), method="POST")

    assert created.status_code == 201
    assert again.status_code == 409
    assert again.json()["code"] == "candidate_exists"
    assert "PUT" in again.json()["hint"]
    assert other_ref.status_code == 201


def test_uuid_mismatch_is_422(client: TestClient) -> None:
    """Ensure the document UUID must equal adr_uuid."""
    other = uuid.uuid4()

    response = push(client, candidate(ADR, content=adr_text(other)))

    assert response.status_code == 422
    assert response.json()["code"] == "uuid_mismatch"
    assert str(other) in response.json()["detail"]


@pytest.mark.parametrize(
    ("content", "issue"),
    [
        ("# No frontmatter\n", "missing_frontmatter"),
        ("---\nuuid: [unclosed\n---\nBody\n", "bad_yaml"),
        ("---\ntitle: No uuid\n---\nBody\n", "missing_uuid"),
        ("---\nuuid: not-a-uuid\n---\nBody\n", "bad_uuid"),
    ],
)
def test_invalid_document_lists_issues(
    client: TestClient, content: str, issue: str
) -> None:
    """Ensure unusable documents are refused with their issue list."""
    response = push(client, candidate(ADR, content=content))

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_document"
    assert issue in {item["code"] for item in body["issues"]}
    assert body["hint"]


def test_lone_surrogate_is_bad_encoding(client: TestClient) -> None:
    """Ensure content that is not encodable as UTF-8 is refused."""
    # Written by hand: json.dumps cannot emit a lone surrogate escape.
    raw = (
        '{"source_id": "central", "project": "platform", '
        f'"adr_uuid": "{ADR}", "ref": "feature/x", '
        '"content": "---\\nuuid: x\\n---\\n\\ud800"}'
    )

    response = client.put(
        "/api/v1/candidates",
        content=raw,
        headers={
            "Authorization": f"Bearer {CENTRAL_TOKEN}",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "bad_encoding"


def test_oversized_content_is_413(client: TestClient) -> None:
    """Ensure content over 1 MiB is refused."""
    big = adr_text(ADR, body="x" * (1024 * 1024))

    response = push(client, candidate(ADR, content=big))

    assert response.status_code == 413
    assert response.json()["code"] == "content_too_large"


def test_out_of_scope_project_is_403(client: TestClient) -> None:
    """Ensure a project outside the registration scope is refused."""
    response = push(client, candidate(ADR, project="elsewhere"))

    assert response.status_code == 403
    assert response.json()["code"] == "project_out_of_scope"


def test_push_disabled_is_403(client: TestClient) -> None:
    """Ensure a registration without push intake refuses pushes."""
    response = push(
        client, candidate(ADR, source_id="pollonly"), token=POLLONLY_TOKEN
    )

    assert response.status_code == 403
    assert response.json()["code"] == "push_disabled"
    assert "intake" in response.json()["hint"]


@pytest.mark.parametrize(
    ("source_id", "token", "code"),
    [
        ("central", None, "not_authenticated"),
        ("central", "wrong-token", "invalid_push_token"),
        ("central", OTHER_TOKEN, "invalid_push_token"),
        ("no-such-source", CENTRAL_TOKEN, "invalid_push_token"),
    ],
)
def test_bad_tokens_are_401(
    client: TestClient, source_id: str, token: str | None, code: str
) -> None:
    """Ensure tokens are checked per registration (401, no leak)."""
    response = push(client, candidate(ADR, source_id=source_id), token=token)

    assert response.status_code == 401
    assert response.json()["code"] == code
    assert response.headers["WWW-Authenticate"].startswith("Bearer")


def test_invalid_body_with_bad_token_is_401(client: TestClient) -> None:
    """Ensure a bad token is refused before the body is validated."""
    response = push(client, {"nonsense": True}, token="wrong-token")

    assert response.status_code == 401


def test_dev_jwt_is_refused_for_intake(client: TestClient) -> None:
    """Ensure an OIDC/dev access token cannot push candidates."""
    token = client.headers["Authorization"].removeprefix("Bearer ")

    response = push(client, candidate(ADR), token=token)

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_push_token"


@pytest.mark.parametrize(
    "path", ["/api/v1/records", "/api/v1/sources", "/api/v1/me"]
)
def test_push_token_cannot_read(client: TestClient, path: str) -> None:
    """Ensure a push token grants no catalog read access."""
    response = client.get(
        path, headers={"Authorization": f"Bearer {CENTRAL_TOKEN}"}
    )

    assert response.status_code == 401


@pytest.mark.parametrize("ref", ["local", "refs/heads/local"])
def test_published_ref_is_refused(client: TestClient, ref: str) -> None:
    """Ensure pushes to the published ref are refused."""
    response = push(client, candidate(ADR, ref=ref))

    assert response.status_code == 422
    assert response.json()["code"] == "published_ref_not_allowed"


def test_candidate_never_overwrites_published(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure a candidate with a published row's UUID/path is separate."""
    path = "doc/decisions/2024-03-01-use-a-catalog.md"
    published_bytes = adr_text(ADR, body="Published text.").encode()
    with provider.lock_registration("central") as store:
        published_id = seed(store, path=path, content=published_bytes)

    response = push(client, candidate(ADR, path=path))

    assert response.status_code == 201
    assert response.json()["record_id"] != str(published_id)
    with provider.unit_of_work() as store:
        published = store.get_record(published_id)
        assert published is not None
        siblings = store.list_identity_siblings(published.identity)
    assert published.kind is RecordState.PUBLISHED
    assert "Published text." in published.rendered_html
    assert {s.kind for s in siblings} == {
        RecordState.PUBLISHED,
        RecordState.CANDIDATE,
    }


def test_delivery_id_is_deduplicated(client: TestClient) -> None:
    """Ensure a repeated delivery id returns the earlier result."""
    first = push(client, candidate(ADR, delivery_id="ci-1"))
    changed = adr_text(ADR, body="Changed in a retry.")

    again = push(client, candidate(ADR, content=changed, delivery_id="ci-1"))

    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json()["deduplicated"] is True
    assert again.json()["digest"] == first.json()["digest"]
    record = client.get(f"/api/v1/records/{first.json()['record_id']}")
    assert record.json()["metadata"]["digest"] == first.json()["digest"]


def test_intake_runs_are_recorded_without_the_token(
    client: TestClient, clean_engine: Engine
) -> None:
    """Ensure success, validation and auth failures all log a run."""
    push(client, candidate(ADR))
    push(client, candidate(ADR, content="# no frontmatter\n"))
    push(client, candidate(ADR), token="wrong-token-value")
    push(client, candidate(ADR), token=None)

    with clean_engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT source_id, status, identity::text, errors::text, "
                "counts::text FROM intake_run WHERE kind = 'push' "
                "ORDER BY started_at"
            )
        ).all()
    assert [(r[0], r[1]) for r in rows] == [
        ("central", "ok"),
        ("central", "failed"),
        ("central", "failed"),
        ("", "failed"),
    ]
    assert "invalid_document" in rows[1][3]
    assert "invalid_push_token" in rows[2][3]
    assert "not_authenticated" in rows[3][3]
    dumped = " ".join(str(value) for row in rows for value in row)
    assert "wrong-token-value" not in dumped
    assert CENTRAL_TOKEN not in dumped


def test_intake_decisions_and_diff_never_open_an_adapter(
    client: TestClient,
    router_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure push, decide, diff and filters make no source calls."""

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("intake/approval must never build an adapter")

    monkeypatch.setattr(filesystem.FilesystemAdapter, "__init__", _refuse)

    pushed = push(client, candidate(ADR)).json()
    as_user(client, router_settings)
    decided = decide(client, pushed["record_id"])
    diff = client.get(f"/api/v1/records/{pushed['record_id']}/diff")
    listed = client.get("/api/v1/records", params={"needs_approval": "true"})

    assert decided.status_code == 201
    assert diff.status_code == 200
    assert listed.status_code == 200
