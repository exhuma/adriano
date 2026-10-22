"""
Tests for cookie authentication and the dev login.

Real HTTP through the app against the test database; sessions come
from ``POST /auth/dev/login``. The OIDC flow is covered by
``tests/routers/oidc``.
"""

import re

import pytest
from sqlalchemy import Engine

from app.auth.dev import DEV_ISSUER
from tests.auth_helpers import IDP_ISSUER, FakeIdp, sign_in
from tests.routers.sessions.support import (
    SESSION_COOKIE,
    ZERO_UUID,
    ClientFactory,
    session_row,
)

PROTECTED_GETS = [
    "/api/v1/records",
    f"/api/v1/records/{ZERO_UUID}",
    "/api/v1/sources",
    "/api/v1/facets",
    "/api/v1/me",
]


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_protected_routes_require_a_session(
    make_client: ClientFactory, path: str
) -> None:
    """Ensure every /api/v1 route answers 401 without a session."""
    client = make_client()

    response = client.get(path)

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_poll_routes_require_a_session(make_client: ClientFactory) -> None:
    """Ensure the operator poll routes answer 401 without a session."""
    client = make_client()

    assert client.post("/api/v1/sources/poll").status_code == 401
    assert client.post("/api/v1/sources/central/poll").status_code == 401


def test_healthz_and_docs_stay_public(make_client: ClientFactory) -> None:
    """Ensure /healthz and the OpenAPI schema need no session."""
    client = make_client()

    health = client.get("/healthz")
    schema = client.get("/openapi.json")

    assert health.status_code == 200
    assert health.json()["auth"] == "dev"
    assert health.json()["rbac"] == "configured"
    assert schema.status_code == 200


def test_unconfigured_auth_answers_503(make_client: ClientFactory) -> None:
    """Ensure no OIDC and no dev auth yields 503, not 200 or a crash."""
    client = make_client(dev_auth_enabled=False, dev_shared_secret=None)
    client.cookies.set(SESSION_COOKIE, "x" * 43)

    response = client.get("/api/v1/records")
    health = client.get("/healthz")

    assert response.status_code == 503
    assert response.json()["code"] == "auth_unconfigured"
    assert "not configured" in response.json()["detail"]
    assert health.json()["auth"] == "unconfigured"


def test_dev_login_sets_the_session_cookie_exactly(
    make_client: ClientFactory,
) -> None:
    """Ensure the session cookie is __Host-, Secure, HttpOnly, Strict."""
    client = make_client()

    response = client.post(
        "/auth/dev/login", json={"sub": "alice", "roles": ["adr-reader"]}
    )

    assert response.status_code == 204
    cookie = response.cookies[SESSION_COOKIE]
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", cookie)
    assert response.headers.get_list("set-cookie") == [
        f"{SESSION_COOKIE}={cookie}; Path=/; Secure; HttpOnly; SameSite=Strict"
    ]


def test_dev_session_authenticates_api_requests(
    make_client: ClientFactory,
) -> None:
    """Ensure a dev session is accepted with the shared claim mapping."""
    client = make_client()
    sign_in(
        client,
        sub="alice",
        name="Alice",
        email="alice@example.com",
        roles=["adr-reader"],
    )

    me = client.get("/api/v1/me")

    assert me.status_code == 200
    assert me.json()["issuer"] == DEV_ISSUER
    assert me.json()["subject"] == "alice"
    assert me.json()["display"] == "Alice"
    assert me.json()["permissions"] == ["read"]


def test_nested_roles_claim_is_supported(make_client: ClientFactory) -> None:
    """Ensure a dotted roles claim path (Keycloak style) is followed."""
    client = make_client(oidc_roles_claim="realm_access.roles")
    sign_in(client, roles=["adr-reader", "x"])

    body = client.get("/api/v1/me").json()

    assert body["roles"] == ["adr-reader", "x"]
    assert body["permissions"] == ["read"]


def test_bearer_token_is_ignored_on_user_routes(
    make_client: ClientFactory,
) -> None:
    """Ensure an Authorization header never authenticates a user."""
    client = make_client(
        oidc_authority=IDP_ISSUER,
        oidc_issuer=IDP_ISSUER,
    )
    token = FakeIdp().token()

    response = client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_unknown_session_is_rejected(make_client: ClientFactory) -> None:
    """Ensure a cookie that names no session is a 401."""
    client = make_client()
    client.cookies.set(SESSION_COOKIE, "A" * 43)

    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["code"] == "session_expired"


def test_malformed_cookie_counts_as_absent(make_client: ClientFactory) -> None:
    """Ensure a cookie value this app never issues is ignored."""
    client = make_client()
    client.cookies.set(SESSION_COOKIE, "not/a;token")

    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_dev_router_is_absent_when_disabled(
    make_client: ClientFactory,
) -> None:
    """Ensure /auth/dev/login is a plain 404 with dev auth disabled."""
    client = make_client(dev_auth_enabled=False)

    response = client.post("/auth/dev/login", json={"sub": "alice"})

    assert response.status_code == 404


def test_dev_router_needs_the_secret(make_client: ClientFactory) -> None:
    """Ensure the dev router is not mounted without a shared secret."""
    client = make_client(dev_shared_secret=None, oidc_authority=IDP_ISSUER)

    response = client.post("/auth/dev/login", json={"sub": "alice"})

    assert response.status_code == 404


def test_dev_session_is_refused_once_dev_auth_is_off(
    make_client: ClientFactory, clean_engine: Engine
) -> None:
    """Ensure dev sessions stop working when dev auth is disabled."""
    cookie = sign_in(make_client())
    later = make_client(
        dev_auth_enabled=False,
        dev_shared_secret=None,
        oidc_authority=IDP_ISSUER,
        oidc_issuer=IDP_ISSUER,
    )
    later.cookies.set(SESSION_COOKIE, cookie)

    response = later.get("/api/v1/me")

    assert response.status_code == 401
    assert session_row(clean_engine, cookie) is None


def test_every_api_route_requires_authentication(
    make_client: ClientFactory,
) -> None:
    """Ensure no /api/v1 route (now or later) is reachable without auth."""
    client = make_client()
    paths: dict[str, dict[str, object]] = client.get("/openapi.json").json()[
        "paths"
    ]
    api = {p: ops for p, ops in paths.items() if p.startswith("/api/v1/")}

    # Candidate intake uses CI push tokens instead of sessions, but it
    # is covered by the same sweep: no credentials -> 401.
    assert set(api["/api/v1/candidates"]) == {"put", "post"}
    assert "/api/v1/records/{record_id}/decisions" in api
    assert "/api/v1/records/{record_id}/diff" in api
    for template, operations in api.items():
        path = re.sub(r"\{[^}]+\}", ZERO_UUID, template)
        for method in operations:
            response = client.request(method.upper(), path)
            assert response.status_code == 401, (method, template)
            assert response.json()["code"] == "not_authenticated"
