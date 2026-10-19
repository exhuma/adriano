"""
Tests for authentication: token routing, validation and 401/503.

Real HTTP through the app against the test database. RS256 tokens come
from :class:`tests.auth_helpers.FakeIdp` (local RSA key, mocked
discovery and JWKS); HS256 tokens from the dev path.
"""

import base64
import datetime
import json
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import app.auth.tokens as tokens_module
from app.auth.deps import get_oidc_validator
from app.auth.dev import DEV_ISSUER
from app.config import Settings, get_settings
from app.main import create_app
from tests.auth_helpers import IDP_ISSUER, TEST_DEV_SECRET, FakeIdp, bearer

type ClientFactory = Callable[..., TestClient]

ZERO_UUID = "00000000-0000-0000-0000-000000000000"

PROTECTED_GETS = [
    "/api/v1/records",
    "/api/v1/records/00000000-0000-0000-0000-000000000000",
    "/api/v1/sources",
    "/api/v1/facets",
    "/api/v1/me",
]


@pytest.fixture
def make_client(
    test_settings: Settings, catalog_file: Path, clean_engine: Engine
) -> Iterator[ClientFactory]:
    """
    Build clients with custom auth settings and an optional fake IdP.

    :param test_settings: Base test settings.
    :param catalog_file: The router tests' ``catalog.yaml``.
    :param clean_engine: Truncated, migrated engine.
    :returns: A factory ``(idp=None, **settings_updates) -> client``.
    """
    stack: list[TestClient] = []

    def _make(idp: FakeIdp | None = None, **updates: Any) -> TestClient:
        settings = test_settings.model_copy(
            update={"config_file": str(catalog_file), **updates}
        )
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        if idp is not None:
            validator = idp.validator(issuer=settings.oidc_issuer)
            app.dependency_overrides[get_oidc_validator] = lambda: validator
        client = TestClient(app)
        client.__enter__()
        stack.append(client)
        return client

    yield _make
    for client in stack:
        client.__exit__(None, None, None)


OIDC = {"oidc_authority": IDP_ISSUER, "oidc_issuer": IDP_ISSUER}


def _auth(token: str) -> dict[str, str]:
    """
    Build an ``Authorization`` header.

    :param token: Raw token.
    :returns: The header mapping.
    """
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_protected_routes_require_a_token(
    make_client: ClientFactory, path: str
) -> None:
    """Ensure every /api/v1 route answers 401 with a Bearer challenge."""
    client = make_client()

    response = client.get(path)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["code"] == "not_authenticated"


def test_poll_routes_require_a_token(make_client: ClientFactory) -> None:
    """Ensure the operator poll routes answer 401 without a token."""
    client = make_client()

    assert client.post("/api/v1/sources/poll").status_code == 401
    assert client.post("/api/v1/sources/central/poll").status_code == 401


def test_healthz_and_docs_stay_public(make_client: ClientFactory) -> None:
    """Ensure /healthz and the OpenAPI schema need no token."""
    client = make_client()

    health = client.get("/healthz")
    schema = client.get("/openapi.json")

    assert health.status_code == 200
    assert health.json()["auth"] == "dev"
    assert health.json()["rbac"] == "configured"
    assert schema.status_code == 200


def test_unconfigured_auth_answers_503(make_client: ClientFactory) -> None:
    """Ensure no OIDC and no dev secret yields 503, not 200 or a crash."""
    client = make_client(dev_auth_enabled=False, dev_shared_secret=None)

    response = client.get("/api/v1/records", headers=_auth("x.y.z"))
    health = client.get("/healthz")

    assert response.status_code == 503
    assert response.json()["code"] == "auth_unconfigured"
    assert "not configured" in response.json()["detail"]
    assert health.json()["auth"] == "unconfigured"


def test_garbage_token_is_rejected(make_client: ClientFactory) -> None:
    """Ensure a malformed token is a 401 invalid_token, never a 500."""
    client = make_client()

    response = client.get("/api/v1/me", headers=_auth("not-a-jwt"))

    assert response.status_code == 401
    assert "invalid_token" in response.headers["WWW-Authenticate"]
    assert response.json()["code"] == "invalid_token"


def test_hs256_is_accepted_with_the_dev_secret(
    make_client: ClientFactory, test_settings: Settings
) -> None:
    """Ensure a dev token is accepted while the dev secret is set."""
    client = make_client()

    response = client.get(
        "/api/v1/me", headers=bearer(test_settings, roles=["adr-reader"])
    )

    assert response.status_code == 200
    assert response.json()["issuer"] == DEV_ISSUER


def test_hs256_is_rejected_without_the_dev_secret(
    make_client: ClientFactory, test_settings: Settings
) -> None:
    """Ensure HS256 tokens are a 401 once the dev secret is unset."""
    client = make_client(
        FakeIdp(), dev_auth_enabled=False, dev_shared_secret=None, **OIDC
    )
    token = bearer(test_settings.model_copy(update=OIDC), roles=["admin"])

    response = client.get("/api/v1/records", headers=token)

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


@pytest.mark.parametrize("alg", ["HS512", "HS384"])
def test_unknown_algorithms_are_rejected(
    make_client: ClientFactory, alg: str
) -> None:
    """Ensure tokens with an algorithm other than RS256/HS256 are 401."""
    client = make_client()
    now = datetime.datetime.now(datetime.UTC)
    token = jwt.encode(
        {
            "iss": DEV_ISSUER,
            "aud": "adr_viewer",
            "sub": "mallory",
            "roles": ["admin"],
            "exp": now + datetime.timedelta(minutes=5),
        },
        TEST_DEV_SECRET,
        algorithm=alg,
    )

    response = client.get("/api/v1/records", headers=_auth(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "unsupported token algorithm"


def test_alg_none_is_rejected(make_client: ClientFactory) -> None:
    """Ensure an unsigned (``alg: none``) token is rejected."""
    client = make_client()
    header = _b64({"alg": "none", "typ": "JWT"})
    payload = _b64(
        {"iss": DEV_ISSUER, "aud": "adr_viewer", "sub": "m", "exp": 9e9}
    )

    response = client.get("/api/v1/me", headers=_auth(f"{header}.{payload}."))

    assert response.status_code == 401
    assert response.json()["detail"] == "unsupported token algorithm"


def _b64(data: dict[str, Any]) -> str:
    """
    Encode a JSON object as unpadded base64url.

    :param data: The object.
    :returns: The encoded segment.
    """
    raw = json.dumps(data).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.mark.parametrize(
    ("claim", "value"),
    [("aud", "another-app"), ("iss", "https://evil.example")],
)
def test_dev_token_with_wrong_aud_or_iss_is_rejected(
    make_client: ClientFactory,
    test_settings: Settings,
    claim: str,
    value: str,
) -> None:
    """Ensure dev tokens enforce the same audience and issuer."""
    client = make_client()
    claims: dict[str, Any] = {
        "iss": DEV_ISSUER,
        "aud": "adr_viewer",
        "sub": "tester",
        "exp": datetime.datetime.now(datetime.UTC)
        + datetime.timedelta(minutes=5),
        claim: value,
    }
    token = jwt.encode(claims, TEST_DEV_SECRET, algorithm="HS256")

    response = client.get("/api/v1/me", headers=_auth(token))

    assert response.status_code == 401


def test_expired_dev_token_is_rejected(make_client: ClientFactory) -> None:
    """Ensure an expired dev token is a 401 token_expired."""
    client = make_client()
    token = jwt.encode(
        {
            "iss": DEV_ISSUER,
            "aud": "adr_viewer",
            "sub": "tester",
            "exp": datetime.datetime.now(datetime.UTC)
            - datetime.timedelta(minutes=1),
        },
        TEST_DEV_SECRET,
        algorithm="HS256",
    )

    response = client.get("/api/v1/me", headers=_auth(token))

    assert response.status_code == 401
    assert response.json()["code"] == "token_expired"


def test_rs256_token_is_accepted_and_never_routed_to_dev(
    make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure a real RS256 token is validated by the JWKS path only."""

    def _forbidden(*_args: object) -> None:
        raise AssertionError("RS256 token routed to the dev validator")

    monkeypatch.setattr(tokens_module, "decode_dev_token", _forbidden)
    idp = FakeIdp()
    client = make_client(idp, **OIDC)

    response = client.get("/api/v1/records", headers=_auth(idp.token()))
    again = client.get("/api/v1/me", headers=_auth(idp.token()))

    assert response.status_code == 200
    assert again.status_code == 200
    assert idp.discovery_calls == 1  # discovery is cached


def test_rs256_issuer_defaults_to_discovery(
    make_client: ClientFactory,
) -> None:
    """Ensure an unset ADRIANO_OIDC_ISSUER uses the discovery issuer."""
    idp = FakeIdp()
    client = make_client(idp, oidc_authority=IDP_ISSUER, oidc_issuer=None)

    ok = client.get("/api/v1/me", headers=_auth(idp.token()))
    bad = client.get(
        "/api/v1/me", headers=_auth(idp.token(iss="https://other"))
    )

    assert ok.status_code == 200
    assert bad.status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "another-app"},
        {"iss": "https://evil.example"},
        {"sub": None},
        {"nbf": datetime.datetime(2999, 1, 1, tzinfo=datetime.UTC)},
    ],
)
def test_rs256_token_with_bad_claims_is_rejected(
    make_client: ClientFactory, overrides: dict[str, Any]
) -> None:
    """Ensure RS256 tokens enforce aud, iss, sub and nbf."""
    idp = FakeIdp()
    client = make_client(idp, **OIDC)

    response = client.get("/api/v1/me", headers=_auth(idp.token(**overrides)))

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_expired_rs256_token_is_rejected(make_client: ClientFactory) -> None:
    """Ensure an expired RS256 token is a 401 token_expired."""
    idp = FakeIdp()
    client = make_client(idp, **OIDC)

    response = client.get(
        "/api/v1/me", headers=_auth(idp.token(expires_in=-60))
    )

    assert response.status_code == 401
    assert response.json()["code"] == "token_expired"


def test_tampered_rs256_signature_is_rejected(
    make_client: ClientFactory,
) -> None:
    """Ensure a token signed by another key under the same kid is 401."""
    idp = FakeIdp()
    client = make_client(idp, **OIDC)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    response = client.get("/api/v1/me", headers=_auth(idp.token(key=other)))

    assert response.status_code == 401


def test_unknown_kid_is_rejected(make_client: ClientFactory) -> None:
    """Ensure a token whose kid is not in the JWKS is a 401."""
    idp = FakeIdp()
    client = make_client(idp, **OIDC)
    stranger = FakeIdp(kid="unknown-kid")

    response = client.get("/api/v1/me", headers=_auth(stranger.token()))

    assert response.status_code == 401


def test_failed_discovery_answers_503(make_client: ClientFactory) -> None:
    """Ensure an unreachable IdP is a 503, retried on the next request."""
    idp = FakeIdp(discovery_status=500)
    client = make_client(idp, **OIDC)

    first = client.get("/api/v1/me", headers=_auth(idp.token()))
    second = client.get("/api/v1/me", headers=_auth(idp.token()))

    assert first.status_code == 503
    assert first.json()["code"] == "auth_unavailable"
    assert second.status_code == 503
    assert idp.discovery_calls == 2


def test_rs256_without_oidc_configured_is_rejected(
    make_client: ClientFactory,
) -> None:
    """Ensure RS256 tokens are a 401 when only dev auth is configured."""
    client = make_client()

    response = client.get("/api/v1/me", headers=_auth(FakeIdp().token()))

    assert response.status_code == 401


def test_dev_and_rs256_tokens_yield_the_same_principal_shape(
    make_client: ClientFactory, test_settings: Settings
) -> None:
    """Ensure dev and real tokens share one identity mapping."""
    idp = FakeIdp()
    client = make_client(idp, **OIDC)
    dev = bearer(
        test_settings.model_copy(update=OIDC),
        sub="alice-123",
        name="Alice",
        email="alice@example.com",
        roles=["admin"],
    )

    real = client.get("/api/v1/me", headers=_auth(idp.token())).json()
    minted = client.get("/api/v1/me", headers=dev).json()

    assert real == minted
    assert real["issuer"] == IDP_ISSUER


def test_nested_roles_claim_is_supported(make_client: ClientFactory) -> None:
    """Ensure a dotted roles claim path (Keycloak style) is followed."""
    idp = FakeIdp()
    client = make_client(idp, oidc_roles_claim="realm_access.roles", **OIDC)
    token = idp.token(
        roles=None, realm_access={"roles": ["adr-reader", 7, "x"]}
    )

    body = client.get("/api/v1/me", headers=_auth(token)).json()

    assert body["roles"] == ["adr-reader", "x"]
    assert body["permissions"] == ["read"]


def test_dev_router_is_absent_when_disabled(
    make_client: ClientFactory,
) -> None:
    """Ensure /auth/dev/token is a plain 404 with dev auth disabled."""
    client = make_client(dev_auth_enabled=False)

    response = client.post("/auth/dev/token", json={"sub": "alice"})

    assert response.status_code == 404


def test_dev_router_needs_the_secret(make_client: ClientFactory) -> None:
    """Ensure the dev router is not mounted without a shared secret."""
    client = make_client(
        FakeIdp(), dev_auth_enabled=True, dev_shared_secret=None, **OIDC
    )

    response = client.post("/auth/dev/token", json={"sub": "alice"})

    assert response.status_code == 404


def test_dev_router_mints_a_usable_token(make_client: ClientFactory) -> None:
    """Ensure the enabled dev router mints a token the API accepts."""
    client = make_client()

    minted = client.post(
        "/auth/dev/token",
        json={
            "sub": "alice",
            "name": "Alice",
            "email": "alice@example.com",
            "roles": ["adr-reader"],
        },
    )
    body = minted.json()
    me = client.get("/api/v1/me", headers=_auth(body["access_token"]))

    assert minted.status_code == 200
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600
    assert me.json()["subject"] == "alice"
    assert me.json()["permissions"] == ["read"]


def test_every_api_route_requires_authentication(
    make_client: ClientFactory,
) -> None:
    """Ensure no /api/v1 route (now or later) is reachable without auth."""
    client = make_client()
    paths: dict[str, dict[str, object]] = client.get("/openapi.json").json()[
        "paths"
    ]
    api = {p: ops for p, ops in paths.items() if p.startswith("/api/v1/")}

    assert len(api) >= 6
    for template, operations in api.items():
        path = re.sub(r"\{[^}]+\}", ZERO_UUID, template)
        for method in operations:
            response = client.request(method.upper(), path)
            assert response.status_code == 401, (method, template)
