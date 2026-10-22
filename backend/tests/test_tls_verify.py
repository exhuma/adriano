"""
Tests for the TLS settings of the outbound HTTPS clients.

The settings are ``ADRIANO_TLS_VERIFY`` and ``ADRIANO_EXTRA_CA_CERTS``.

Each client talks to a real local HTTPS server whose certificate is
self-signed, i.e. issued by a CA the client does not trust -- the
situation of an instance behind an internal certificate authority.
With verification on the request must fail, unless that certificate is
trusted as an extra CA; with verification off it must succeed.
"""

import json
import ssl
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth.oidc import (
    OidcValidator,
    _default_jwks_client,
    cached_oidc_validator,
)
from app.errors import AuthUnavailableError
from app.sources.gitlab_api import open_client
from app.tls import outbound_ssl_context
from tests.tls_helpers import write_self_signed

#: One public signing key, so the body is a valid (non-empty) JWKS.
_JWK = jwt.algorithms.ECAlgorithm.to_jwk(
    ec.generate_private_key(ec.SECP256R1()).public_key(), as_dict=True
)

#: Body served for every path: valid as a discovery document, a JWKS
#: document and a GitLab JSON response alike.
_BODY = {
    "issuer": "https://127.0.0.1",
    "jwks_uri": "https://127.0.0.1/jwks",
    "keys": [_JWK],
}


class _JsonHandler(BaseHTTPRequestHandler):
    """Answer every GET with :data:`_BODY`."""

    def do_GET(self) -> None:
        """Send the JSON body."""
        payload = json.dumps(_BODY).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Keep the test output quiet."""


@dataclass(frozen=True)
class UntrustedServer:
    """
    A local HTTPS server with a self-signed certificate.

    :param url: The server's base URL.
    :param cert_path: Its certificate (PEM), which is its own CA.
    """

    url: str
    cert_path: Path


@pytest.fixture
def untrusted_server(tmp_path: Path) -> Iterator[UntrustedServer]:
    """
    Serve :data:`_BODY` over HTTPS with an untrusted certificate.

    :param tmp_path: Pytest temporary directory.
    :returns: The server's URL and certificate path.
    """
    cert_path, key_path = write_self_signed(tmp_path)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _JsonHandler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield UntrustedServer(
            f"https://127.0.0.1:{server.server_address[1]}", cert_path
        )
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def untrusted_https(untrusted_server: UntrustedServer) -> str:
    """
    Return the base URL of :func:`untrusted_server`.

    :param untrusted_server: The server.
    :returns: Its base URL.
    """
    return untrusted_server.url


@pytest.fixture
def trusting_context(untrusted_server: UntrustedServer) -> ssl.SSLContext:
    """
    Build a verifying context that trusts the server's certificate.

    :param untrusted_server: The server.
    :returns: The context, with the certificate as an extra CA.
    """
    return outbound_ssl_context(True, (untrusted_server.cert_path,))


def test_discovery_rejects_untrusted_certificate(untrusted_https: str) -> None:
    """Ensure OIDC discovery fails on an untrusted certificate by default."""
    validator = OidcValidator(untrusted_https, None, "aud")

    with pytest.raises(AuthUnavailableError):
        validator._fetch_discovery()


def test_discovery_skips_verification_when_disabled(
    untrusted_https: str,
) -> None:
    """Ensure an unverified context fetches discovery anyway."""
    validator = OidcValidator(
        untrusted_https, None, "aud", ssl_context=outbound_ssl_context(False)
    )

    document = validator._fetch_discovery()

    assert document["jwks_uri"] == _BODY["jwks_uri"]


def test_jwks_rejects_untrusted_certificate(untrusted_https: str) -> None:
    """Ensure the JWKS fetch fails on an untrusted certificate by default."""
    client = _default_jwks_client(f"{untrusted_https}/jwks")

    with pytest.raises(jwt.PyJWKClientConnectionError):
        client.fetch_data()


def test_jwks_skips_verification_when_disabled(untrusted_https: str) -> None:
    """Ensure an unverified context fetches the JWKS anyway."""
    client = _default_jwks_client(
        f"{untrusted_https}/jwks", ssl_context=outbound_ssl_context(False)
    )

    assert client.fetch_data()["keys"] == [_JWK]


async def test_gitlab_rejects_untrusted_certificate(
    untrusted_https: str,
) -> None:
    """Ensure the GitLab client fails on an untrusted certificate."""
    async with open_client(untrusted_https, "token") as client:
        with pytest.raises(httpx.ConnectError):
            await client.get("version")


async def test_gitlab_skips_verification_when_disabled(
    untrusted_https: str,
) -> None:
    """Ensure an unverified context reaches GitLab anyway."""
    async with open_client(
        untrusted_https, "token", ssl_context=outbound_ssl_context(False)
    ) as client:
        response = await client.get("version")

    assert response.status_code == 200


def test_discovery_trusts_extra_ca(
    untrusted_https: str, trusting_context: ssl.SSLContext
) -> None:
    """Ensure OIDC discovery succeeds when the CA is an extra CA."""
    validator = OidcValidator(
        untrusted_https, None, "aud", ssl_context=trusting_context
    )

    document = validator._fetch_discovery()

    assert document["jwks_uri"] == _BODY["jwks_uri"]


def test_jwks_trusts_extra_ca(
    untrusted_https: str, trusting_context: ssl.SSLContext
) -> None:
    """Ensure the JWKS fetch succeeds when the CA is an extra CA."""
    client = _default_jwks_client(
        f"{untrusted_https}/jwks", ssl_context=trusting_context
    )

    assert client.fetch_data()["keys"] == [_JWK]


async def test_gitlab_trusts_extra_ca(
    untrusted_https: str, trusting_context: ssl.SSLContext
) -> None:
    """Ensure the GitLab client succeeds when the CA is an extra CA."""
    async with open_client(
        untrusted_https, "token", ssl_context=trusting_context
    ) as client:
        response = await client.get("version")

    assert response.status_code == 200


def test_cached_validator_uses_extra_ca(
    untrusted_server: UntrustedServer,
) -> None:
    """Ensure the cached validator builds its context from the settings."""
    cached_oidc_validator.cache_clear()
    validator = cached_oidc_validator(
        untrusted_server.url, None, "aud", True, (untrusted_server.cert_path,)
    )

    document = validator._fetch_discovery()

    assert document["issuer"] == _BODY["issuer"]
