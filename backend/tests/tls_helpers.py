"""Helpers for TLS tests: self-signed certificates written to disk."""

import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def write_self_signed(
    tmp_path: Path, stem: str = "cert", *, ca: bool = False
) -> tuple[Path, Path]:
    """
    Write a self-signed certificate for 127.0.0.1 and its key.

    The certificate is its own issuer, so it is also the CA to trust.

    :param tmp_path: Directory to write into.
    :param stem: Base name of the written files.
    :param ca: Whether to mark it as a CA (``basicConstraints``), which
        makes OpenSSL count it in ``cert_store_stats()["x509_ca"]``.
    :returns: Certificate and key paths.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.UTC)
    builder = (
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
    )
    if ca:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
    cert = builder.sign(key, hashes.SHA256())
    cert_path = tmp_path / f"{stem}.pem"
    key_path = tmp_path / f"{stem}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path
