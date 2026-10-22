"""Tests for the inline token refresh and the OIDC sign-out."""

import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.auth_helpers import CLIENT_ID, END_SESSION_URL, FakeIdp
from tests.routers.oidc.support import (
    SESSION_COOKIE,
    expire_access_token,
    query_of,
    session_rows,
    sign_in_at_idp,
    stored_refresh_token,
    wait_for_lock_waiter,
)


def test_expiring_access_token_is_refreshed_with_rotation(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure an expiring token is refreshed inline and rotated."""
    cookie = sign_in_at_idp(client, idp).cookies[SESSION_COOKIE]
    first_refresh = stored_refresh_token(clean_engine)
    expire_access_token(clean_engine, cookie)

    response = client.get("/api/v1/me")
    again = client.get("/api/v1/records")

    (row,) = session_rows(clean_engine)
    assert response.status_code == 200
    assert again.status_code == 200
    assert idp.refresh_calls == 1
    assert stored_refresh_token(clean_engine) != first_refresh
    assert first_refresh not in idp.refresh_tokens  # spent at the IdP
    assert row["access_expires_at"] > datetime.datetime.now(
        datetime.UTC
    ) + datetime.timedelta(minutes=4)


def test_parallel_requests_refresh_once(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure two parallel requests make a single IdP refresh call."""
    cookie = sign_in_at_idp(client, idp).cookies[SESSION_COOKIE]
    expire_access_token(clean_engine, cookie)
    start = threading.Barrier(2)
    idp.on_refresh = lambda: wait_for_lock_waiter(clean_engine)

    def _request(path: str) -> int:
        start.wait(timeout=10)
        return client.get(path).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(_request, ["/api/v1/me", "/api/v1/records"]))

    assert statuses == [200, 200]
    assert idp.refresh_calls == 1


def test_invalid_grant_ends_the_session(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure a refused refresh is a 401 and deletes the session."""
    cookie = sign_in_at_idp(client, idp).cookies[SESSION_COOKIE]
    expire_access_token(clean_engine, cookie)
    idp.refresh_error = "invalid_grant"

    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["code"] == "session_expired"
    assert session_rows(clean_engine) == []


def test_unreachable_idp_keeps_the_session(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure a refresh against an unreachable IdP is a 503."""
    cookie = sign_in_at_idp(client, idp).cookies[SESSION_COOKIE]
    expire_access_token(clean_engine, cookie)
    idp.token_unreachable = True

    response = client.get("/api/v1/me")

    assert response.status_code == 503
    assert response.json()["code"] == "auth_unavailable"
    assert len(session_rows(clean_engine)) == 1


def test_session_check_never_refreshes(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure /auth/session does not call the IdP."""
    cookie = sign_in_at_idp(client, idp).cookies[SESSION_COOKIE]
    expire_access_token(clean_engine, cookie)

    response = client.get("/auth/session")

    assert response.json()["authenticated"] is True
    assert idp.refresh_calls == 0


def test_logout_revokes_and_returns_the_end_session_url(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure logout revokes, ends the session and names the IdP logout."""
    sign_in_at_idp(client, idp)
    refresh = stored_refresh_token(clean_engine)

    response = client.post("/auth/logout")

    url = response.json()["end_session_url"]
    query = query_of(url)
    assert response.status_code == 200
    assert url.startswith(END_SESSION_URL + "?")
    assert query["client_id"] == CLIENT_ID
    assert query["post_logout_redirect_uri"] == "https://testserver/"
    assert query["id_token_hint"].count(".") == 2
    assert idp.revoked == [refresh]
    assert session_rows(clean_engine) == []
    assert response.headers["set-cookie"].startswith(f"{SESSION_COOKIE}=;")
    assert client.get("/api/v1/me").status_code == 401
