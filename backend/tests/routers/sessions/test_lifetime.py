"""Tests for ``/auth/session``, idle/absolute expiry and logout."""

import datetime

from sqlalchemy import Engine

from app.services.session_values import utc_now
from tests.auth_helpers import (
    SESSION_COOKIE,
    ClientFactory,
    session_row,
    sign_in,
)
from tests.routers.sessions.support import (
    set_session_times,
)


def test_session_endpoint_without_a_session(
    make_client: ClientFactory,
) -> None:
    """Ensure /auth/session answers 200 unauthenticated without a cookie."""
    client = make_client(csrf=False)

    response = client.get("/auth/session")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_session_endpoint_with_a_session(make_client: ClientFactory) -> None:
    """Ensure /auth/session reports an active session and its expiry."""
    client = make_client(csrf=False)
    sign_in(client)

    response = client.get("/auth/session")

    body = response.json()
    expires = datetime.datetime.fromisoformat(body["expires_at"])
    assert response.status_code == 200
    assert body["authenticated"] is True
    remaining = expires - utc_now()
    assert (
        datetime.timedelta(hours=7) < remaining <= datetime.timedelta(hours=8)
    )


def test_session_endpoint_with_an_expired_session(
    make_client: ClientFactory, clean_engine: Engine
) -> None:
    """Ensure /auth/session reports an expired session as signed out."""
    client = make_client()
    cookie = sign_in(client)
    set_session_times(
        clean_engine, cookie, idle_expires_at=utc_now() - datetime.timedelta(1)
    )

    assert client.get("/auth/session").json() == {"authenticated": False}


def test_idle_expiry_ends_the_session(
    make_client: ClientFactory, clean_engine: Engine
) -> None:
    """Ensure a session idle past its idle expiry is a 401 and deleted."""
    client = make_client()
    cookie = sign_in(client, roles=["admin"])
    set_session_times(
        clean_engine,
        cookie,
        idle_expires_at=utc_now() - datetime.timedelta(seconds=1),
    )

    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["code"] == "session_expired"
    assert session_row(clean_engine, cookie) is None


def test_recent_activity_is_not_rewritten(
    make_client: ClientFactory, clean_engine: Engine
) -> None:
    """Ensure requests within a minute do not touch the session row."""
    client = make_client()
    cookie = sign_in(client, roles=["admin"])
    before = session_row(clean_engine, cookie)

    client.get("/api/v1/me")
    client.get("/api/v1/records")

    assert session_row(clean_engine, cookie) == before


def test_dev_logout_ends_the_session_and_clears_the_cookie(
    make_client: ClientFactory, clean_engine: Engine
) -> None:
    """Ensure logout deletes the session and expires the cookie."""
    client = make_client()
    cookie = sign_in(client, roles=["admin"])

    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"end_session_url": None}
    assert response.headers.get_list("set-cookie") == [
        f"{SESSION_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; "
        "Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
    ]
    assert session_row(clean_engine, cookie) is None
    client.cookies.set(SESSION_COOKIE, cookie)
    assert client.get("/api/v1/me").status_code == 401


def test_logout_without_a_session_is_harmless(
    make_client: ClientFactory,
) -> None:
    """Ensure logout without a cookie still answers 200."""
    client = make_client()

    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"end_session_url": None}
