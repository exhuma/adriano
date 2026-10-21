"""
Tests for ``ADRIANO_TLS_VERIFY`` on the outbound HTTPS clients.

Each client talks to a real local HTTPS server whose certificate is
self-signed, i.e. issued by a CA the client does not trust -- the
situation of an instance behind an internal certificate authority.
With verification on the request must fail; with it off it must
succeed.
"""

import datetime
import ipaddress
import json
import ssl
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.auth.oidc import OidcValidator, _default_jwks_client
from app.errors import AuthUnavailableError
from app.sources.gitlab_api import open_client

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


def _self_signed(tmp_path: Path) -> tuple[Path, Path]:
    """
    Write a self-signed certificate for 127.0.0.1 and its key.

    :param tmp_path: Directory to write into.
    :returns: Certificate and key paths.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


@pytest.fixture
def untrusted_https(tmp_path: Path) -> Iterator[str]:
    """
    Serve :data:`_BODY` over HTTPS with an untrusted certificate.

    :param tmp_path: Pytest temporary directory.
    :returns: The server's base URL.
    """
    cert_path, key_path = _self_signed(tmp_path)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _JsonHandler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def test_discovery_rejects_untrusted_certificate(untrusted_https: str) -> None:
    """Ensure OIDC discovery fails on an untrusted certificate by default."""
    validator = OidcValidator(untrusted_https, None, "aud")

    with pytest.raises(AuthUnavailableError):
        validator._fetch_discovery()


def test_discovery_skips_verification_when_disabled(
    untrusted_https: str,
) -> None:
    """Ensure tls_verify=False fetches discovery despite the certificate."""
    validator = OidcValidator(untrusted_https, None, "aud", tls_verify=False)

    document = validator._fetch_discovery()

    assert document["jwks_uri"] == _BODY["jwks_uri"]


def test_jwks_rejects_untrusted_certificate(untrusted_https: str) -> None:
    """Ensure the JWKS fetch fails on an untrusted certificate by default."""
    client = _default_jwks_client(f"{untrusted_https}/jwks")

    with pytest.raises(jwt.PyJWKClientConnectionError):
        client.fetch_data()


def test_jwks_skips_verification_when_disabled(untrusted_https: str) -> None:
    """Ensure tls_verify=False fetches the JWKS despite the certificate."""
    client = _default_jwks_client(f"{untrusted_https}/jwks", tls_verify=False)

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
    """Ensure tls_verify=False reaches GitLab despite the certificate."""
    async with open_client(
        untrusted_https, "token", tls_verify=False
    ) as client:
        response = await client.get("version")

    assert response.status_code == 200
