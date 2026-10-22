"""
Helpers for authenticated test requests.

- :func:`https_client` builds a :class:`TestClient` on
  ``https://testserver`` (so the ``Secure`` session cookie is sent)
  that adds the ``X-Adriano-CSRF: 1`` header to unsafe requests.
- :func:`sign_in` signs a client in through ``POST /auth/dev/login``
  (the real dev-session path); the session cookie stays in the
  client's jar.
- :class:`FakeIdp` poses as an OIDC provider: a locally generated RSA
  key, and discovery, token and revocation endpoints answered through
  ``httpx.MockTransport`` (the JWKS is served through a real
  :class:`jwt.PyJWKClient`). No test talks to a real identity provider.

:data:`TEST_DEV_SECRET` and :data:`TEST_SESSION_KEY` are throwaway
values used only by the test suite; they are never a default anywhere
in the application.
"""

import base64
import datetime
import hashlib
import secrets
import urllib.parse
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from pydantic import SecretStr

from app.auth.csrf import CSRF_HEADER, UNSAFE_METHODS
from app.auth.idp import IdpClient
from app.auth.oidc import OidcValidator

#: Dev shared secret of the test settings (tests only).
TEST_DEV_SECRET = "test-only-dev-secret-" + "0123456789abcdef" * 3

#: Session key of the test settings (tests only).
TEST_SESSION_KEY = "c26RjuiSkW-H31dbUTEt_ELLnCSNmUjhxoMLsnRrJIU="

#: Base URL of every test client (``Secure`` cookies need https).
BASE_URL = "https://testserver"

#: Client id and secret of the fake IdP's confidential client.
CLIENT_ID = "adriano"
CLIENT_SECRET = "test-only-client-secret"


def _add_csrf_header(request: httpx.Request) -> None:
    """
    Add the CSRF header to unsafe requests that do not set it.

    :param request: The outgoing request.
    """
    if request.method in UNSAFE_METHODS and CSRF_HEADER not in request.headers:
        request.headers[CSRF_HEADER] = "1"


def https_client(app: FastAPI, *, csrf: bool = True) -> TestClient:
    """
    Build an un-entered https test client.

    :param app: The application.
    :param csrf: Add the CSRF header to unsafe requests.
    :returns: The client.
    """
    client = TestClient(app, base_url=BASE_URL)
    if csrf:
        client.event_hooks = {"request": [_add_csrf_header], "response": []}
    return client


def sign_in(
    client: TestClient,
    *,
    sub: str = "tester",
    roles: Sequence[str] = (),
    name: str | None = "Test User",
    email: str | None = "tester@example.com",
) -> str:
    """
    Sign *client* in with a dev session (replacing any other).

    :param client: A client of an app with dev auth enabled.
    :param sub: Subject.
    :param roles: Roles.
    :param name: Display name.
    :param email: Email.
    :returns: The session cookie value.
    """
    response = client.post(
        "/auth/dev/login",
        json={"sub": sub, "roles": list(roles), "name": name, "email": email},
        headers={CSRF_HEADER: "1"},
    )
    assert response.status_code == 204, response.text
    cookie = response.cookies.get("__Host-adriano-session")
    assert cookie
    return cookie


#: Issuer / authority of the fake IdP used by the RS256 tests.
IDP_ISSUER = "https://idp.test/realms/adr"

#: Base URL of the fake IdP's OIDC endpoints.
IDP_BASE = f"{IDP_ISSUER}/protocol/openid-connect"
AUTHORIZE_URL = f"{IDP_BASE}/auth"
END_SESSION_URL = f"{IDP_BASE}/logout"


def pkce_challenge(verifier: str) -> str:
    """
    Compute a PKCE ``S256`` challenge (independently of the app).

    :param verifier: The code verifier.
    :returns: The challenge.
    """
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class _LocalJwksClient(jwt.PyJWKClient):
    """A real :class:`jwt.PyJWKClient` serving a local key set."""

    def __init__(self, uri: str, jwks: dict[str, Any]) -> None:
        """
        Store the key set.

        :param uri: JWKS URI (from the fake discovery document).
        :param jwks: The key set to serve.
        """
        super().__init__(uri)
        self._local = jwks
        self.fetches = 0

    def fetch_data(self) -> Any:
        """
        Serve the local key set instead of an HTTP fetch.

        :returns: The key set.
        """
        self.fetches += 1
        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(self._local)
        return self._local


def _key() -> rsa.RSAPrivateKey:
    """
    Generate a test RSA key.

    :returns: The key.
    """
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@dataclass
class _Grant:
    """
    An issued authorization code.

    :param sub: Subject it signs in.
    :param nonce: Nonce to put into the ID token.
    :param challenge: PKCE challenge of the authorization request.
    :param redirect_uri: Redirect URI of the authorization request.
    """

    sub: str
    nonce: str
    challenge: str
    redirect_uri: str


@dataclass
class FakeIdp:
    """
    A locally generated RSA key pair posing as an OIDC provider.

    :param kid: Key id published in the JWKS.
    :param discovery_status: HTTP status of the discovery endpoint.
    :param auth_methods: ``token_endpoint_auth_methods_supported``
        (``None`` omits it).
    :param access_ttl: Lifetime in seconds of issued access tokens.
    :param refresh_error: OAuth error the token endpoint answers to
        refresh requests (``None``: refresh works).
    :param token_unreachable: Make the token endpoint unreachable.
    :param on_refresh: Called on every refresh request before it is
        answered (tests coordinate concurrency with it).
    """

    kid: str = "test-key-1"
    discovery_status: int = 200
    key: rsa.RSAPrivateKey = field(default_factory=_key)
    discovery_calls: int = 0
    auth_methods: list[str] | None = None
    access_ttl: int = 300
    refresh_error: str | None = None
    token_unreachable: bool = False
    on_refresh: Callable[[], None] | None = None
    token_requests: list[httpx.Request] = field(default_factory=list)
    refresh_calls: int = 0
    revoked: list[str] = field(default_factory=list)
    access_overrides: dict[str, Any] = field(default_factory=dict)
    codes: dict[str, _Grant] = field(default_factory=dict)
    refresh_tokens: dict[str, str] = field(default_factory=dict)

    def jwks(self) -> dict[str, Any]:
        """
        Publish the public key.

        :returns: The JWKS document.
        """
        jwk = RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
        jwk.update({"kid": self.kid, "use": "sig", "alg": "RS256"})
        return {"keys": [jwk]}

    def _discovery(self, request: httpx.Request) -> httpx.Response:
        """
        Answer the discovery request.

        :param request: The request.
        :returns: The discovery document (or the configured error).
        """
        self.discovery_calls += 1
        assert request.url.path.endswith("/.well-known/openid-configuration")
        if self.discovery_status != 200:
            return httpx.Response(self.discovery_status)
        document: dict[str, Any] = {
            "issuer": IDP_ISSUER,
            "jwks_uri": f"{IDP_BASE}/certs",
            "authorization_endpoint": AUTHORIZE_URL,
            "token_endpoint": f"{IDP_BASE}/token",
            "revocation_endpoint": f"{IDP_BASE}/revoke",
            "end_session_endpoint": END_SESSION_URL,
        }
        if self.auth_methods is not None:
            document["token_endpoint_auth_methods_supported"] = (
                self.auth_methods
            )
        return httpx.Response(200, json=document)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        """
        Route a mocked request to the fake endpoint.

        :param request: The request.
        :returns: The response.
        """
        path = request.url.path
        if path.endswith("/token"):
            return self._token(request)
        if path.endswith("/revoke"):
            form = urllib.parse.parse_qs(request.content.decode())
            self.revoked.append(form["token"][0])
            return httpx.Response(200)
        return self._discovery(request)

    def transport(self) -> httpx.MockTransport:
        """
        Build the mocked transport of every endpoint.

        :returns: The transport.
        """
        return httpx.MockTransport(self._handle)

    def client_credentials(self, request: httpx.Request) -> tuple[str, str]:
        """
        Read the client authentication of a token request.

        :param request: The request.
        :returns: Client id and secret (basic or post).
        """
        header = request.headers.get("authorization", "")
        if header.startswith("Basic "):
            pair = base64.b64decode(header.removeprefix("Basic ")).decode()
            client_id, _, secret = pair.partition(":")
            return (
                urllib.parse.unquote(client_id),
                urllib.parse.unquote(secret),
            )
        form = urllib.parse.parse_qs(request.content.decode())
        return form["client_id"][0], form["client_secret"][0]

    def _token(self, request: httpx.Request) -> httpx.Response:
        """
        Answer a token request (code exchange or refresh).

        :param request: The request.
        :returns: The token response or an OAuth error.
        """
        if self.token_unreachable:
            raise httpx.ConnectError("unreachable", request=request)
        self.token_requests.append(request)
        if self.client_credentials(request) != (CLIENT_ID, CLIENT_SECRET):
            return httpx.Response(401, json={"error": "invalid_client"})
        form = {
            k: v[0]
            for k, v in urllib.parse.parse_qs(request.content.decode()).items()
        }
        if form["grant_type"] == "refresh_token":
            return self._refresh(form)
        grant = self.codes.pop(form["code"], None)
        if (
            grant is None
            or grant.redirect_uri != form["redirect_uri"]
            or pkce_challenge(form["code_verifier"]) != grant.challenge
        ):
            return httpx.Response(400, json={"error": "invalid_grant"})
        return self._issue(grant.sub, nonce=grant.nonce)

    def _refresh(self, form: dict[str, str]) -> httpx.Response:
        """
        Answer a refresh request, rotating the refresh token.

        :param form: The request form.
        :returns: The token response or an OAuth error.
        """
        self.refresh_calls += 1
        if self.on_refresh is not None:
            self.on_refresh()
        if self.refresh_error is not None:
            return httpx.Response(400, json={"error": self.refresh_error})
        sub = self.refresh_tokens.pop(form["refresh_token"], None)
        if sub is None:
            return httpx.Response(400, json={"error": "invalid_grant"})
        return self._issue(sub, nonce=None)

    def _issue(self, sub: str, *, nonce: str | None) -> httpx.Response:
        """
        Issue an access, refresh and ID token.

        :param sub: Subject.
        :param nonce: Nonce for the ID token (``None``: no ID token).
        :returns: The token response.
        """
        refresh = secrets.token_urlsafe(24)
        self.refresh_tokens[refresh] = sub
        body: dict[str, Any] = {
            "access_token": self.token(
                expires_in=self.access_ttl,
                **{"sub": sub, **self.access_overrides},
            ),
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": self.access_ttl,
        }
        if nonce is not None:
            body["id_token"] = self.token(
                sub=sub, aud=CLIENT_ID, nonce=nonce, roles=None
            )
        return httpx.Response(200, json=body)

    def authorize(
        self,
        authorize_url: str,
        *,
        sub: str = "alice-123",
        nonce: str | None = None,
    ) -> tuple[str, str]:
        """
        Act as the user approving an authorization request.

        :param authorize_url: The ``Location`` of ``/auth/login``.
        :param sub: Subject to sign in.
        :param nonce: Nonce to put into the ID token (default: the
            requested one).
        :returns: The code and the state for the callback.
        """
        query = dict(
            urllib.parse.parse_qsl(urllib.parse.urlsplit(authorize_url).query)
        )
        code = secrets.token_urlsafe(16)
        self.codes[code] = _Grant(
            sub=sub,
            nonce=nonce or query["nonce"],
            challenge=query["code_challenge"],
            redirect_uri=query["redirect_uri"],
        )
        return code, query["state"]

    def validator(
        self, issuer: str | None = IDP_ISSUER, audience: str = "adr_viewer"
    ) -> OidcValidator:
        """
        Build a real validator wired to this fake IdP (no network).

        :param issuer: Expected issuer (``None``: from discovery).
        :param audience: Expected audience.
        :returns: The validator.
        """
        jwks = self.jwks()
        return OidcValidator(
            IDP_ISSUER,
            issuer,
            audience,
            transport=self.transport(),
            jwks_client_factory=lambda uri: _LocalJwksClient(uri, jwks),
        )

    def idp_client(self, validator: OidcValidator) -> IdpClient:
        """
        Build the confidential client wired to this fake IdP.

        :param validator: Validator from :meth:`validator`.
        :returns: The client.
        """
        return IdpClient(
            validator,
            client_id=CLIENT_ID,
            client_secret=SecretStr(CLIENT_SECRET),
            scope="openid profile email offline_access",
            transport=self.transport(),
        )

    def token(
        self,
        *,
        key: rsa.RSAPrivateKey | None = None,
        expires_in: int = 300,
        **overrides: Any,
    ) -> str:
        """
        Sign an RS256 token.

        :param key: Signing key (default: the published one).
        :param expires_in: Seconds until ``exp`` (negative: expired).
        :param overrides: Claims to set (``None`` removes a claim).
        :returns: The token.
        """
        now = datetime.datetime.now(datetime.UTC)
        claims: dict[str, Any] = {
            "iss": IDP_ISSUER,
            "aud": "adr_viewer",
            "sub": "alice-123",
            "name": "Alice",
            "email": "alice@example.com",
            "roles": ["admin"],
            "iat": now,
            "exp": now + datetime.timedelta(seconds=expires_in),
        }
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(
            claims,
            key or self.key,
            algorithm="RS256",
            headers={"kid": self.kid},
        )
