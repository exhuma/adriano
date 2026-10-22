"""Helpers of the OIDC router tests: sign-in steps and raw session rows."""

import datetime
import time
import urllib.parse
from collections.abc import Callable
from typing import Any

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, text

from app.auth.cipher import SessionCipher
from app.services.auth_sessions import session_id_for
from tests.auth_helpers import (
    CLIENT_ID,
    CLIENT_SECRET,
    IDP_ISSUER,
    TEST_SESSION_KEY,
    FakeIdp,
)

type ClientFactory = Callable[..., TestClient]

SESSION_COOKIE = "__Host-adriano-session"
LOGIN_COOKIE = "__Host-adriano-login"

#: Settings of an app signing in at the fake IdP (dev auth off).
OIDC = {
    "oidc_authority": IDP_ISSUER,
    "oidc_issuer": IDP_ISSUER,
    "oidc_client_id": CLIENT_ID,
    "oidc_client_secret": SecretStr(CLIENT_SECRET),
    "dev_auth_enabled": False,
    "dev_shared_secret": None,
}


def start_login(client: TestClient, return_to: str | None = None) -> str:
    """
    Start a sign-in.

    :param client: Test client.
    :param return_to: ``return_to`` query parameter.
    :returns: The authorization URL (``Location``).
    """
    params = {} if return_to is None else {"return_to": return_to}
    response = client.get("/auth/login", params=params, follow_redirects=False)
    assert response.status_code == 302
    return response.headers["location"]


def query_of(url: str) -> dict[str, str]:
    """
    Parse the query of a URL.

    :param url: The URL.
    :returns: Its parameters.
    """
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


def sign_in_at_idp(
    client: TestClient, idp: FakeIdp, return_to: str | None = None
) -> httpx.Response:
    """
    Run a complete sign-in.

    :param client: Test client.
    :param idp: The fake IdP.
    :param return_to: Requested return path.
    :returns: The callback response.
    """
    code, state = idp.authorize(start_login(client, return_to))
    return client.get("/auth/callback", params={"code": code, "state": state})


def session_rows(engine: Engine) -> list[dict[str, Any]]:
    """
    Read every raw session row.

    :param engine: Test database engine.
    :returns: The rows.
    """
    with engine.connect() as connection:
        result = connection.execute(text("SELECT * FROM auth_session"))
        return [dict(row) for row in result.mappings()]


def stored_refresh_token(engine: Engine) -> str:
    """
    Decrypt the refresh token of the only session.

    :param engine: Test database engine.
    :returns: The refresh token.
    """
    (row,) = session_rows(engine)
    cipher = SessionCipher(SecretStr(TEST_SESSION_KEY))
    return cipher.decrypt(row["refresh_token"])


def expire_access_token(engine: Engine, cookie: str) -> None:
    """
    Make the stored access token expire within the refresh margin.

    :param engine: Test database engine.
    :param cookie: Session cookie value.
    """
    soon = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=5)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE auth_session SET access_expires_at = :soon "
                "WHERE id = :id"
            ),
            {"soon": soon, "id": session_id_for(cookie)},
        )


def wait_for_lock_waiter(engine: Engine) -> None:
    """
    Block until another connection waits for a row lock.

    :param engine: Test database engine.
    :raises AssertionError: If no waiter shows up within 10 seconds.
    """
    deadline = time.monotonic() + 10
    query = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() AND wait_event_type = 'Lock'"
    )
    with engine.connect() as connection:
        while time.monotonic() < deadline:
            waiting = connection.execute(query).scalar_one()
            # pg_stat_activity is a per-transaction snapshot.
            connection.rollback()
            if waiting > 0:
                return
            time.sleep(0.01)
    raise AssertionError("no request waited for the session row lock")
