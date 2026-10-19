"""
Helpers for authenticated test requests.

Dev HS256 tokens (:func:`bearer`) and a fake OIDC provider
(:class:`FakeIdp`: locally generated RSA key, mocked discovery via
``httpx.MockTransport``, local JWKS served through a real
:class:`jwt.PyJWKClient`). No test talks to a real identity provider.

:data:`TEST_DEV_SECRET` is a throwaway value used only by the test
suite; it is never a default anywhere in the application.
"""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.auth.dev import DevIdentity, mint_dev_token
from app.auth.oidc import OidcValidator
from app.config import Settings

#: Dev shared secret of the test settings (tests only).
TEST_DEV_SECRET = "test-only-dev-secret-" + "0123456789abcdef" * 3


def bearer(
    settings: Settings,
    *,
    sub: str = "tester",
    roles: Sequence[str] = (),
    name: str | None = "Test User",
    email: str | None = "tester@example.com",
) -> dict[str, str]:
    """
    Build an ``Authorization`` header with a dev token.

    :param settings: Settings holding the dev secret.
    :param sub: Token subject.
    :param roles: Roles.
    :param name: Display name.
    :param email: Email.
    :returns: The header mapping.
    """
    identity = DevIdentity(sub=sub, name=name, email=email, roles=roles)
    token = mint_dev_token(settings, identity)
    return {"Authorization": f"Bearer {token}"}


#: Issuer / authority of the fake IdP used by the RS256 tests.
IDP_ISSUER = "https://idp.test/realms/adr"


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


@dataclass
class FakeIdp:
    """
    A locally generated RSA key pair posing as an OIDC provider.

    :param kid: Key id published in the JWKS.
    :param discovery_status: HTTP status of the discovery endpoint.
    """

    kid: str = "test-key-1"
    discovery_status: int = 200
    key: rsa.RSAPrivateKey = field(
        default_factory=lambda: rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
    )
    discovery_calls: int = 0

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
        return httpx.Response(
            200,
            json={
                "issuer": IDP_ISSUER,
                "jwks_uri": f"{IDP_ISSUER}/protocol/openid-connect/certs",
            },
        )

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
            transport=httpx.MockTransport(self._discovery),
            jwks_client_factory=lambda uri: _LocalJwksClient(uri, jwks),
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
