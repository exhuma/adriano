"""
The TLS context shared by every outbound HTTPS client.

The OIDC discovery request and the GitLab client (httpx) and the JWKS
fetch (PyJWT) all use the :class:`ssl.SSLContext` built here, so they
trust exactly the same certificate authorities.

Trust store, with verification on (``ADRIANO_TLS_VERIFY``, the
default):

- **Base:** the Mozilla bundle shipped with ``certifi``. When the
  ``SSL_CERT_FILE`` environment variable is set, that file replaces it;
  otherwise, when ``SSL_CERT_DIR`` is set, that directory replaces it.
  This is the precedence httpx itself applies, so setting either
  variable keeps its documented "replace the standard set" meaning.
- **Extra CAs** (``ADRIANO_EXTRA_CA_CERTS``): every certificate in the
  configured PEM files (bundles allowed) and in the ``*.pem`` and
  ``*.crt`` files of the configured directories is added on top of the
  base, so public endpoints keep working. Each file is parsed with
  ``cryptography`` first; an unreadable file, a file without a PEM
  certificate or a directory without matching files raises
  :class:`~app.errors.ConfigurationError` naming it. The added
  certificates are logged at INFO with their subjects.

With verification off the context checks neither certificates nor
host names, and the extra CAs are ignored; one warning says so.

:func:`outbound_ssl_context` is cached per argument pair, so a process
builds each context (and logs about it) once. Processes build it at
startup (:func:`app.cli.main`, :func:`app.main.create_app`) so a bad
CA file stops them instead of failing the first login or poll.

Public API: :func:`outbound_ssl_context`,
:func:`ssl_context_from_settings`, :func:`unverified_ssl_context`.
"""

import logging
import os
import ssl
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import certifi
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding

from app.config import Settings
from app.errors import ConfigurationError

__all__ = [
    "outbound_ssl_context",
    "ssl_context_from_settings",
    "unverified_ssl_context",
]

#: File name suffixes loaded from an ``ADRIANO_EXTRA_CA_CERTS``
#: directory.
CA_FILE_SUFFIXES = (".pem", ".crt")

logger = logging.getLogger(__name__)


def unverified_ssl_context() -> ssl.SSLContext:
    """
    Build a TLS context that skips certificate and hostname checks.

    Used only when ``ADRIANO_TLS_VERIFY`` is false.

    :returns: The context.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _base_context() -> ssl.SSLContext:
    """
    Build a verifying context with the base trust store.

    :returns: The context, trusting ``SSL_CERT_FILE``, else
        ``SSL_CERT_DIR``, else the ``certifi`` bundle.
    """
    cert_file = os.environ.get("SSL_CERT_FILE")
    if cert_file:
        return ssl.create_default_context(cafile=cert_file)
    cert_dir = os.environ.get("SSL_CERT_DIR")
    if cert_dir:
        return ssl.create_default_context(capath=cert_dir)
    return ssl.create_default_context(cafile=certifi.where())


def _ca_files(path: Path) -> list[Path]:
    """
    Expand one configured path into the files to load.

    :param path: A PEM file or a directory.
    :returns: *path* itself, or the directory's ``*.pem`` and ``*.crt``
        files in name order.
    :raises ConfigurationError: If a directory holds no such file.
    """
    if not path.is_dir():
        return [path]
    files = sorted(
        p
        for p in path.iterdir()
        if p.is_file() and p.suffix.lower() in CA_FILE_SUFFIXES
    )
    if not files:
        raise ConfigurationError(
            f"ADRIANO_EXTRA_CA_CERTS: directory {path} contains no "
            f"{' or '.join('*' + s for s in CA_FILE_SUFFIXES)} file"
        )
    return files


def _read_certificates(path: Path) -> list[x509.Certificate]:
    """
    Parse every PEM certificate of one file.

    :param path: The file.
    :returns: Its certificates, at least one.
    :raises ConfigurationError: If the file cannot be read or holds no
        PEM certificate.
    """
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ConfigurationError(
            f"ADRIANO_EXTRA_CA_CERTS: cannot read {path} "
            f"({exc.strerror or type(exc).__name__})"
        ) from exc
    try:
        return x509.load_pem_x509_certificates(data)
    except ValueError as exc:
        raise ConfigurationError(
            f"ADRIANO_EXTRA_CA_CERTS: {path} contains no valid PEM certificate"
        ) from exc


def _load_extra_cas(
    context: ssl.SSLContext, paths: Iterable[Path]
) -> list[x509.Certificate]:
    """
    Add the certificates of the configured paths to a context.

    :param context: The context to extend.
    :param paths: Configured files and directories.
    :returns: The added certificates.
    :raises ConfigurationError: If a path cannot be loaded.
    """
    added: list[x509.Certificate] = []
    for path in paths:
        for file in _ca_files(path):
            certificates = _read_certificates(file)
            pem = "".join(
                cert.public_bytes(Encoding.PEM).decode("ascii")
                for cert in certificates
            )
            context.load_verify_locations(cadata=pem)
            added.extend(certificates)
    return added


def _warn_unverified(extra_ca_certs: tuple[Path, ...]) -> None:
    """
    Log the single warning about disabled verification.

    :param extra_ca_certs: Configured extra CA paths (ignored).
    """
    ignored = (
        " ADRIANO_EXTRA_CA_CERTS is set but ignored while verification is off."
        if extra_ca_certs
        else ""
    )
    logger.warning(
        "ADRIANO_TLS_VERIFY is false: certificates of the OIDC provider "
        "and of network sources (such as GitLab) are NOT verified. Never "
        "use this in production.%s",
        ignored,
    )


@lru_cache(maxsize=4)
def outbound_ssl_context(
    verify: bool = True, extra_ca_certs: tuple[Path, ...] = ()
) -> ssl.SSLContext:
    """
    Build (once per arguments) the context for outbound HTTPS.

    :param verify: Whether to verify server certificates and host
        names (``ADRIANO_TLS_VERIFY``).
    :param extra_ca_certs: PEM files and directories whose
        certificates are trusted in addition to the base store
        (``ADRIANO_EXTRA_CA_CERTS``); ignored when *verify* is false.
    :returns: The shared context; callers must not modify it.
    :raises ConfigurationError: If an extra CA path cannot be loaded.
    """
    if not verify:
        _warn_unverified(extra_ca_certs)
        return unverified_ssl_context()
    context = _base_context()
    added = _load_extra_cas(context, extra_ca_certs)
    if added:
        logger.info(
            "trusting %d extra CA certificate(s) from "
            "ADRIANO_EXTRA_CA_CERTS: %s",
            len(added),
            "; ".join(cert.subject.rfc4514_string() for cert in added),
        )
    return context


def ssl_context_from_settings(settings: Settings) -> ssl.SSLContext:
    """
    Return the outbound context for the application settings.

    :param settings: Application settings.
    :returns: The shared context (see :func:`outbound_ssl_context`).
    :raises ConfigurationError: If an extra CA path cannot be loaded.
    """
    return outbound_ssl_context(
        settings.tls_verify, settings.extra_ca_certs or ()
    )
