"""Tests for the CSRF protection of cookie-authenticated requests."""

import pytest
from sqlalchemy import Engine

from tests.auth_helpers import sign_in
from tests.routers.sessions.support import (
    SESSION_COOKIE,
    ZERO_UUID,
    ClientFactory,
    session_row,
)


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Adriano-CSRF": "0"},
        {"X-Adriano-CSRF": "1", "Origin": "https://evil.example"},
        {"X-Adriano-CSRF": "1", "Origin": "http://testserver"},
        {"X-Adriano-CSRF": "1", "Origin": "null"},
    ],
)
def test_dev_login_requires_csrf(
    make_client: ClientFactory, headers: dict[str, str]
) -> None:
    """Ensure the dev login refuses a missing header or foreign Origin."""
    client = make_client(csrf=False)

    response = client.post(
        "/auth/dev/login", json={"sub": "alice"}, headers=headers
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
    assert SESSION_COOKIE not in response.cookies


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/sources/poll",
        f"/api/v1/records/{ZERO_UUID}/decisions",
    ],
)
def test_unsafe_api_requests_without_csrf_header_are_403(
    make_client: ClientFactory, path: str
) -> None:
    """Ensure a cookie-authenticated POST needs the CSRF header."""
    client = make_client(csrf=False)
    sign_in(client, roles=["admin"])

    response = client.post(path, json={"action": "accepted"})

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_foreign_origin_is_403(make_client: ClientFactory) -> None:
    """Ensure a cookie-authenticated POST from another origin is refused."""
    client = make_client()
    sign_in(client, roles=["admin"])

    response = client.post(
        "/api/v1/sources/poll", headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


@pytest.mark.parametrize(
    "origin", [None, "https://testserver", "https://TESTSERVER:443"]
)
def test_same_origin_post_with_header_passes(
    make_client: ClientFactory, origin: str | None
) -> None:
    """Ensure the header plus an absent or same Origin is accepted."""
    client = make_client()
    sign_in(client, roles=["admin"])
    headers = {"Origin": origin} if origin else {}

    response = client.post("/api/v1/sources/poll", headers=headers)

    assert response.status_code == 202


def test_safe_requests_need_no_csrf_header(make_client: ClientFactory) -> None:
    """Ensure GET requests with a session need no CSRF header."""
    client = make_client(csrf=False)
    sign_in(client, roles=["admin"])

    assert client.get("/api/v1/records").status_code == 200


def test_logout_requires_csrf(
    make_client: ClientFactory, clean_engine: Engine
) -> None:
    """Ensure logout without the CSRF header keeps the session."""
    client = make_client(csrf=False)
    cookie = sign_in(client)

    response = client.post("/auth/logout")

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
    assert session_row(clean_engine, cookie) is not None
