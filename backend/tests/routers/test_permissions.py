"""
Tests for authorization (``read`` / ``operate``) and ``GET /api/v1/me``.

Roles from the router tests' ``catalog.yaml``: ``admin`` (read,
operate), ``adr-reader`` (read), ``poller`` (operate only); the policy
lists the ``adr-reviewer`` role as reviewer.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.auth.dev import DEV_ISSUER
from tests.auth_helpers import sign_in

type AsRoles = Callable[..., None]


@pytest.fixture
def as_roles(client: TestClient) -> AsRoles:
    """
    Switch the client to a dev session with other roles.

    :param client: The test client.
    :returns: ``as_roles(*roles)``.
    """

    def _switch(*roles: str) -> None:
        sign_in(client, roles=roles)

    return _switch


@pytest.mark.parametrize(
    "path", ["/api/v1/records", "/api/v1/sources", "/api/v1/facets"]
)
def test_reader_can_browse(
    client: TestClient, as_roles: AsRoles, path: str
) -> None:
    """Ensure the read permission opens the browse routes."""
    as_roles("adr-reader")

    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    "path", ["/api/v1/records", "/api/v1/sources", "/api/v1/facets"]
)
def test_roles_without_read_are_forbidden(
    client: TestClient, as_roles: AsRoles, path: str
) -> None:
    """Ensure operate-only and unknown roles cannot browse (403)."""
    as_roles("poller", "unknown-role")

    response = client.get(path)

    assert response.status_code == 403
    assert response.json()["code"] == "permission_required"
    assert "'read'" in response.json()["detail"]


def test_reader_cannot_poll(client: TestClient, as_roles: AsRoles) -> None:
    """Ensure read permission never allows a poll (403 naming operate)."""
    as_roles("adr-reader")

    every = client.post("/api/v1/sources/poll")
    one = client.post("/api/v1/sources/central/poll")

    assert every.status_code == 403
    assert one.status_code == 403
    assert "'operate'" in every.json()["detail"]


def test_me_describes_the_caller(client: TestClient) -> None:
    """Ensure /me returns identity, permissions and reviewer status."""
    response = client.get("/api/v1/me")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "issuer": DEV_ISSUER,
        "subject": "tester",
        "display": "Test User",
        "email": "tester@example.com",
        "roles": ["admin"],
        "permissions": ["operate", "read"],
        "reviewer": {
            "eligible": False,
            "reason": body["reviewer"]["reason"],
        },
    }
    assert "not a reviewer" in body["reviewer"]["reason"]


def test_me_reports_reviewer_eligibility(
    client: TestClient, as_roles: AsRoles
) -> None:
    """Ensure a policy reviewer role makes /me report eligibility."""
    as_roles("adr-reviewer")

    body = client.get("/api/v1/me").json()

    assert body["reviewer"]["eligible"] is True
    assert body["permissions"] == []


def test_me_needs_no_permission(client: TestClient, as_roles: AsRoles) -> None:
    """Ensure a user without roles can still read /me."""
    as_roles()

    response = client.get("/api/v1/me")

    assert response.status_code == 200
    assert response.json()["roles"] == []
    assert response.json()["permissions"] == []
