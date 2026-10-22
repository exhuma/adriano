"""
Tests for :mod:`app.tls`, the shared outbound TLS context.

No network: the tests inspect the context's trust store and the errors
and log lines of the builder, and the startup hooks that build it.
"""

import io
import logging
import ssl
from pathlib import Path

import certifi
import pytest

from app.cli import EXIT_USAGE, main
from app.config import Settings
from app.errors import ConfigurationError
from app.main import create_app
from app.tls import outbound_ssl_context, ssl_context_from_settings
from tests.tls_helpers import write_self_signed


def _ca_count(context: ssl.SSLContext) -> int:
    """
    Count the CA certificates loaded into a context.

    :param context: The context.
    :returns: The number of CA certificates in its store.
    """
    return context.cert_store_stats()["x509_ca"]


@pytest.fixture(autouse=True)
def _fresh_tls_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Start from no cached context and no trust store override.

    Removes the OpenSSL overrides a developer may export.

    :param monkeypatch: Pytest monkeypatch.
    """
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    outbound_ssl_context.cache_clear()


@pytest.fixture
def ca_file(tmp_path: Path) -> Path:
    """
    Write one self-signed CA certificate.

    :param tmp_path: Pytest temporary directory.
    :returns: Its PEM file.
    """
    return write_self_signed(tmp_path, ca=True)[0]


def test_default_context_uses_certifi() -> None:
    """Ensure the default context trusts the certifi bundle."""
    expected = ssl.create_default_context(cafile=certifi.where())

    context = outbound_ssl_context()

    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert _ca_count(context) == _ca_count(expected)


def test_extra_ca_is_added_to_default_bundle(ca_file: Path) -> None:
    """Ensure an extra CA is trusted on top of the default bundle."""
    default = _ca_count(outbound_ssl_context())

    context = outbound_ssl_context(True, (ca_file,))

    assert _ca_count(context) == default + 1
    assert default > 1


def test_bundle_file_adds_every_certificate(tmp_path: Path) -> None:
    """Ensure every certificate of a PEM bundle is trusted."""
    first = write_self_signed(tmp_path, "one", ca=True)[0]
    second = write_self_signed(tmp_path, "two", ca=True)[0]
    bundle = tmp_path / "bundle.pem"
    bundle.write_bytes(first.read_bytes() + second.read_bytes())
    default = _ca_count(outbound_ssl_context())

    context = outbound_ssl_context(True, (bundle,))

    assert _ca_count(context) == default + 2


def test_directory_loads_pem_and_crt_files(tmp_path: Path) -> None:
    """Ensure a directory contributes its *.pem and *.crt files only."""
    certs = tmp_path / "certs"
    certs.mkdir()
    write_self_signed(certs, "one", ca=True)
    crt = write_self_signed(tmp_path, "two", ca=True)[0]
    (certs / "two.crt").write_bytes(crt.read_bytes())
    (certs / "notes.txt").write_text("not a certificate")
    default = _ca_count(outbound_ssl_context())

    context = outbound_ssl_context(True, (certs,))

    assert _ca_count(context) == default + 2


def test_directory_without_certificates_is_rejected(tmp_path: Path) -> None:
    """Ensure a directory with no *.pem or *.crt file names itself."""
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "readme.txt").write_text("nothing here")

    with pytest.raises(ConfigurationError, match=str(empty)):
        outbound_ssl_context(True, (empty,))


@pytest.mark.parametrize(
    "content",
    [b"", b"not a certificate\n", b"-----BEGIN CERTIFICATE-----\nZZ\n"],
    ids=["empty", "text", "broken-pem"],
)
def test_file_without_certificate_is_rejected(
    tmp_path: Path, content: bytes
) -> None:
    """Ensure a file without a PEM certificate fails, naming the file."""
    bad = tmp_path / "bad.pem"
    bad.write_bytes(content)

    with pytest.raises(ConfigurationError) as excinfo:
        outbound_ssl_context(True, (bad,))

    assert excinfo.value.message.startswith("ADRIANO_EXTRA_CA_CERTS")
    assert str(bad) in excinfo.value.message


def test_bad_file_in_directory_is_named(tmp_path: Path) -> None:
    """Ensure a broken file inside a directory is named in the error."""
    certs = tmp_path / "certs"
    certs.mkdir()
    write_self_signed(certs, "good", ca=True)
    bad = certs / "bad.crt"
    bad.write_text("garbage")

    with pytest.raises(ConfigurationError, match=str(bad)):
        outbound_ssl_context(True, (certs,))


def test_unreadable_file_is_rejected(tmp_path: Path) -> None:
    """Ensure a path that cannot be read fails, naming the path."""
    missing = tmp_path / "gone.pem"

    with pytest.raises(ConfigurationError, match=str(missing)):
        outbound_ssl_context(True, (missing,))


def test_added_certificates_are_logged(
    ca_file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure the count and subjects of extra CAs are logged at INFO."""
    caplog.set_level(logging.INFO, logger="app.tls")

    outbound_ssl_context(True, (ca_file,))

    assert "1 extra CA certificate(s)" in caplog.text
    assert "CN=127.0.0.1" in caplog.text


def test_unverified_context_ignores_extra_ca(
    ca_file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure verify=False skips checks and warns that extras are ignored."""
    caplog.set_level(logging.WARNING, logger="app.tls")

    context = outbound_ssl_context(False, (ca_file,))

    assert context.verify_mode is ssl.CERT_NONE
    assert context.check_hostname is False
    assert "ADRIANO_TLS_VERIFY is false" in caplog.text
    assert "ADRIANO_EXTRA_CA_CERTS is set but ignored" in caplog.text


def test_ssl_cert_file_replaces_default_bundle(
    ca_file: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ensure SSL_CERT_FILE replaces the certifi bundle as the base."""
    monkeypatch.setenv("SSL_CERT_FILE", str(ca_file))
    extra = write_self_signed(tmp_path, "extra", ca=True)[0]

    context = outbound_ssl_context(True, (extra,))

    assert _ca_count(context) == 2


def test_context_from_settings_is_shared(
    test_settings: Settings, ca_file: Path
) -> None:
    """Ensure equal settings share one cached context."""
    settings = test_settings.model_copy(update={"extra_ca_certs": (ca_file,)})

    first = ssl_context_from_settings(settings)

    assert ssl_context_from_settings(settings.model_copy()) is first
    assert first is outbound_ssl_context(True, (ca_file,))


def _bad_ca_settings(test_settings: Settings, tmp_path: Path) -> Settings:
    """
    Point settings at an extra CA file that holds no certificate.

    :param test_settings: Test settings.
    :param tmp_path: Directory for the file.
    :returns: Updated settings.
    """
    bad = tmp_path / "bad.pem"
    bad.write_text("not a certificate")
    return test_settings.model_copy(update={"extra_ca_certs": (bad,)})


def test_cli_fails_on_bad_ca_file(
    test_settings: Settings,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ensure check-config stops with a usage error on a bad CA file."""
    settings = _bad_ca_settings(test_settings, tmp_path)

    code = main(["check-config"], settings=settings, out=io.StringIO())

    assert code == EXIT_USAGE
    assert "ADRIANO_EXTRA_CA_CERTS" in capsys.readouterr().err


def test_create_app_fails_on_bad_ca_file(
    test_settings: Settings, tmp_path: Path
) -> None:
    """Ensure building the web app fails on a bad CA file."""
    settings = _bad_ca_settings(test_settings, tmp_path)

    with pytest.raises(ConfigurationError, match="ADRIANO_EXTRA_CA_CERTS"):
        create_app(settings)
