"""
Tests for the operator poll routes (``POST /api/v1/sources[/{id}]/poll``).

The module overrides ``catalog_file`` with a real on-disk filesystem
source (``central``, one ADR), a push-only registration (``pushonly``)
and the default admin client (read + operate).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

CATALOG = """
sources:
  - id: central
    type: filesystem
    root: ./root
    published_ref: local
  - id: pushonly
    type: filesystem
    root: ./root
    published_ref: local
    intake: [push]
    push_tokens_env: [ADRIANO_PUSH_TOKEN_PUSHONLY]
approval_policy:
  id: global
  version: 1
  reviewers:
    roles: [adr-reviewer]
rbac:
  roles:
    admin: [read, operate]
"""

ADR = b"""---
uuid: 6f1c1a64-2d1e-4d4a-9a49-3f1f0f1d2a01
title: Use a catalog
decision-date: 2024-01-01
---
Body.
"""


@pytest.fixture
def catalog_file(tmp_path: Path) -> Path:
    """
    Write a catalog with one pollable and one push-only registration.

    :param tmp_path: Pytest temporary directory.
    :returns: The file path.
    """
    decisions = tmp_path / "root" / "platform" / "doc" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "2024-01-01-use-a-catalog.md").write_bytes(ADR)
    path = tmp_path / "catalog.yaml"
    path.write_text(CATALOG, encoding="utf-8")
    return path


def _central(client: TestClient) -> dict[str, object]:
    """
    Read the ``central`` registration status.

    :param client: The test client.
    :returns: Its ``/api/v1/sources`` entry.
    """
    sources = client.get("/api/v1/sources").json()
    return next(s for s in sources if s["id"] == "central")


def test_poll_all_is_accepted_and_runs(client: TestClient) -> None:
    """Ensure POST /sources/poll answers 202 and the poll completes."""
    assert _central(client)["last_attempt_at"] is None

    response = client.post("/api/v1/sources/poll")

    assert response.status_code == 202
    assert response.json()["accepted"] == ["central"]
    assert "GET /api/v1/sources" in response.json()["message"]
    central = _central(client)
    assert central["last_attempt_at"] is not None
    assert central["last_status"] == "ok"
    records = client.get("/api/v1/records").json()
    assert records["total"] == 1


def test_poll_one_is_accepted(client: TestClient) -> None:
    """Ensure POST /sources/{id}/poll answers 202 for that id."""
    response = client.post("/api/v1/sources/central/poll")

    assert response.status_code == 202
    assert response.json()["accepted"] == ["central"]
    assert _central(client)["last_status"] == "ok"


def test_poll_unknown_source_is_404(client: TestClient) -> None:
    """Ensure polling an unconfigured id is a 404."""
    response = client.post("/api/v1/sources/nope/poll")

    assert response.status_code == 404
    assert response.json()["code"] == "unknown_source"


def test_poll_push_only_source_is_409(client: TestClient) -> None:
    """Ensure a registration without poll intake is a 409 with reason."""
    response = client.post("/api/v1/sources/pushonly/poll")

    assert response.status_code == 409
    assert response.json()["code"] == "not_pollable"
    assert "pushonly" in response.json()["detail"]
