"""Tests for the OIDC sign-in: login redirect, callback, cookies, state."""

import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.auth_helpers import (
    AUTHORIZE_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    IDP_ISSUER,
    FakeIdp,
)
from tests.routers.oidc.support import (
    LOGIN_COOKIE,
    SESSION_COOKIE,
    ClientFactory,
    query_of,
    session_rows,
    sign_in_at_idp,
    start_login,
    stored_refresh_token,
)


def test_login_redirects_with_pkce_state_and_nonce(
    client: TestClient,
) -> None:
    """Ensure /auth/login redirects with code + PKCE S256 + state + nonce."""
    response = client.get("/auth/login", follow_redirects=False)

    location = response.headers["location"]
    query = query_of(location)
    assert response.status_code == 302
    assert location.startswith(AUTHORIZE_URL + "?")
    assert query["response_type"] == "code"
    assert query["client_id"] == CLIENT_ID
    assert query["redirect_uri"] == "https://testserver/auth/callback"
    assert query["scope"] == "openid profile email offline_access"
    assert query["code_challenge_method"] == "S256"
    assert len(query["code_challenge"]) == 43
    assert len(query["state"]) >= 43
    assert len(query["nonce"]) >= 43
    assert query["state"] != query["nonce"]
    assert response.headers["cache-control"] == "no-store"


def test_login_binds_the_state_with_a_lax_cookie(client: TestClient) -> None:
    """Ensure the sign-in binding cookie has exact flags and lifetime."""
    response = client.get("/auth/login", follow_redirects=False)

    state = query_of(response.headers["location"])["state"]
    assert response.headers.get_list("set-cookie") == [
        f"{LOGIN_COOKIE}={state}; Path=/; Secure; HttpOnly; SameSite=Lax; "
        "Max-Age=600"
    ]


def test_login_is_404_without_oidc(make_client: ClientFactory) -> None:
    """Ensure /auth/login and /auth/callback are 404 without OIDC."""
    client = make_client(oidc_authority=None, dev_auth_enabled=True)

    assert client.get("/auth/login").status_code == 404
    assert client.get("/auth/callback").status_code == 404


def test_callback_creates_a_session_with_exact_cookie_flags(
    client: TestClient, idp: FakeIdp
) -> None:
    """Ensure a good callback sets the session cookie and a landing page."""
    response = sign_in_at_idp(client, idp, "/records/central/x?tab=history")

    cookies = response.headers.get_list("set-cookie")
    session = response.cookies[SESSION_COOKIE]
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert cookies == [
        f"{SESSION_COOKIE}={session}; Path=/; Secure; HttpOnly; "
        "SameSite=Strict",
        f"{LOGIN_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Lax; "
        "Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT",
    ]
    assert '<script src="/auth/landing.js" defer></script>' in response.text
    assert 'data-return-to="/records/central/x?tab=history"' in response.text


def test_signed_in_user_reaches_the_api(
    client: TestClient, idp: FakeIdp
) -> None:
    """Ensure the session carries the validated access-token identity."""
    sign_in_at_idp(client, idp)

    me = client.get("/api/v1/me")
    session = client.get("/auth/session").json()

    assert me.status_code == 200
    assert me.json()["issuer"] == IDP_ISSUER
    assert me.json()["subject"] == "alice-123"
    assert me.json()["permissions"] == ["operate", "read"]
    assert session["authenticated"] is True


def test_token_endpoint_uses_client_secret_basic(
    client: TestClient, idp: FakeIdp
) -> None:
    """Ensure the code exchange authenticates with HTTP Basic."""
    sign_in_at_idp(client, idp)

    (request,) = idp.token_requests
    form = query_of("?" + request.content.decode())
    assert request.headers["authorization"].startswith("Basic ")
    assert "client_secret" not in form
    assert form["grant_type"] == "authorization_code"
    assert form["redirect_uri"] == "https://testserver/auth/callback"


def test_token_endpoint_uses_post_when_only_post_is_offered(
    client: TestClient, idp: FakeIdp
) -> None:
    """Ensure client_secret_post is used when discovery lists only it."""
    idp.auth_methods = ["client_secret_post"]

    response = sign_in_at_idp(client, idp)

    (request,) = idp.token_requests
    form = query_of("?" + request.content.decode())
    assert response.status_code == 200
    assert "authorization" not in request.headers
    assert form["client_secret"] == CLIENT_SECRET


@pytest.mark.parametrize(
    "return_to",
    [
        "https://evil.example/x",
        "//evil.example/x",
        "/\\evil.example",
        "javascript:alert(1)",
        "records",
        "/a\nb",
    ],
)
def test_invalid_return_to_becomes_root(
    client: TestClient, idp: FakeIdp, return_to: str
) -> None:
    """Ensure a non-relative or ambiguous return_to is replaced by /."""
    response = sign_in_at_idp(client, idp, return_to)

    assert response.status_code == 200
    assert 'data-return-to="/"' in response.text


def test_return_to_is_html_escaped(client: TestClient, idp: FakeIdp) -> None:
    """Ensure a return path cannot break out of the attribute."""
    response = sign_in_at_idp(client, idp, '/x"><script>alert(1)</script>')

    assert "<script>alert" not in response.text
    assert "&quot;&gt;&lt;script&gt;" in response.text


def test_state_reuse_is_rejected(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure a callback state works exactly once."""
    location = start_login(client)
    code, state = idp.authorize(location)
    first = client.get("/auth/callback", params={"code": code, "state": state})
    client.cookies.clear()
    client.cookies.set(LOGIN_COOKIE, state)
    code_again, _ = idp.authorize(location)

    replay = client.get(
        "/auth/callback", params={"code": code_again, "state": state}
    )

    assert first.status_code == 200
    assert replay.status_code == 400
    assert "already used" in replay.text
    assert SESSION_COOKIE not in replay.cookies
    assert len(idp.token_requests) == 1
    assert len(session_rows(clean_engine)) == 1


def test_state_must_match_the_binding_cookie(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure a callback in a browser that did not start it fails."""
    code, state = idp.authorize(start_login(client))
    client.cookies.clear()

    response = client.get(
        "/auth/callback", params={"code": code, "state": state}
    )

    assert response.status_code == 400
    assert "Sign-in failed" in response.text
    assert idp.token_requests == []
    assert session_rows(clean_engine) == []


def test_nonce_mismatch_is_rejected(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure an ID token with another nonce creates no session."""
    code, state = idp.authorize(
        start_login(client), nonce="someone-elses-nonce"
    )

    response = client.get(
        "/auth/callback", params={"code": code, "state": state}
    )

    assert response.status_code == 400
    assert SESSION_COOKIE not in response.cookies
    assert session_rows(clean_engine) == []


def test_access_token_for_another_audience_is_rejected(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure the access token is validated with the OidcValidator."""
    idp.access_overrides = {"aud": "another-api"}

    response = sign_in_at_idp(client, idp)

    assert response.status_code == 400
    assert session_rows(clean_engine) == []


def test_idp_error_is_a_400_page(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure an IdP error parameter answers the error page."""
    _, state = idp.authorize(start_login(client))

    response = client.get(
        "/auth/callback", params={"error": "access_denied", "state": state}
    )

    assert response.status_code == 400
    assert "access_denied" in response.text
    assert session_rows(clean_engine) == []


def test_landing_script_is_javascript(client: TestClient) -> None:
    """Ensure /auth/landing.js is served as text/javascript."""
    response = client.get("/auth/landing.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert "location.replace" in response.text


def test_session_is_encrypted_at_rest(
    client: TestClient, idp: FakeIdp, clean_engine: Engine
) -> None:
    """Ensure the raw row holds no token and no cookie value in clear."""
    response = sign_in_at_idp(client, idp)
    cookie = response.cookies[SESSION_COOKIE]
    (row,) = session_rows(clean_engine)
    raw = " ".join(str(value) for value in row.values())
    refresh = stored_refresh_token(clean_engine)

    assert row["id"] == hashlib.sha256(cookie.encode()).hexdigest()
    assert row["kind"] == "oidc"
    assert cookie not in raw
    assert refresh not in raw
    assert "eyJ" not in raw.replace(row["claims"], "")  # no JWT in clear
    assert "alice@example.com" not in raw
