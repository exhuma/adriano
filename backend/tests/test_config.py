"""
Tests for :class:`app.config.Settings` environment parsing.

Settings are built from an empty working directory so a developer's
``.env`` never leaks into the assertions.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings
from tests.auth_helpers import IDP_ISSUER, TEST_SESSION_KEY, FakeIdp

BLANK_OPTIONAL = [
    "ADRIANO_OIDC_AUTHORITY",
    "ADRIANO_OIDC_ISSUER",
    "ADRIANO_OIDC_CLIENT_ID",
    "ADRIANO_OIDC_CLIENT_SECRET",
    "ADRIANO_DEV_SHARED_SECRET",
    "ADRIANO_SESSION_KEY",
    "ADRIANO_STATIC_DIR",
    "ADRIANO_FORWARDED_ALLOW_IPS",
    "ADRIANO_EXTRA_CA_CERTS",
]

#: A complete OIDC client configuration.
OIDC_ENV = {
    "ADRIANO_OIDC_AUTHORITY": "https://idp.example.com/realms/adr",
    "ADRIANO_OIDC_CLIENT_ID": "adriano",
    "ADRIANO_OIDC_CLIENT_SECRET": "s3cret",
    "ADRIANO_SESSION_KEY": TEST_SESSION_KEY,
}


def _set_env(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    """
    Export several settings.

    :param monkeypatch: Pytest monkeypatch.
    :param values: Variable names and values.
    """
    for name, value in values.items():
        monkeypatch.setenv(name, value)


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Run each test from an empty directory (no ``.env`` to read).

    :param monkeypatch: Pytest monkeypatch.
    :param tmp_path: Pytest temporary directory.
    """
    monkeypatch.chdir(tmp_path)


@pytest.mark.parametrize("name", BLANK_OPTIONAL)
@pytest.mark.parametrize("raw", ["", "   "])
def test_blank_optional_setting_is_none(
    monkeypatch: pytest.MonkeyPatch, name: str, raw: str
) -> None:
    """Ensure an empty or blank optional env var is treated as unset."""
    monkeypatch.setenv(name, raw)

    settings = Settings()

    field = name.removeprefix("ADRIANO_").lower()
    assert getattr(settings, field) is None


def test_non_blank_optional_setting_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure a real optional value passes through unchanged."""
    monkeypatch.setenv("ADRIANO_OIDC_ISSUER", IDP_ISSUER)

    settings = Settings()

    assert settings.oidc_issuer == IDP_ISSUER


def test_empty_issuer_env_validates_against_discovery_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure ADRIANO_OIDC_ISSUER="" falls back to the discovery issuer."""
    _set_env(monkeypatch, {**OIDC_ENV, "ADRIANO_OIDC_AUTHORITY": IDP_ISSUER})
    monkeypatch.setenv("ADRIANO_OIDC_ISSUER", "")
    settings = Settings()
    idp = FakeIdp()
    validator = idp.validator(issuer=settings.oidc_issuer)

    claims = validator.decode(idp.token())

    assert claims["iss"] == IDP_ISSUER
    assert claims["sub"] == "alice-123"


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure a missing ADRIANO_DATABASE_URL fails settings validation."""
    monkeypatch.delenv("ADRIANO_DATABASE_URL")

    with pytest.raises(ValidationError, match="database_url"):
        Settings()


@pytest.mark.parametrize(
    "authority",
    [
        "https://idp.example.com",
        "https://idp.example.com/realms/adr",
        "http://127.0.0.1:8080/realms/adr",
        "https://login.example.com:8443/",
    ],
)
def test_well_formed_authority_is_accepted(
    monkeypatch: pytest.MonkeyPatch, authority: str
) -> None:
    """Ensure http(s)://host[:port][/path] authorities are accepted."""
    _set_env(monkeypatch, {**OIDC_ENV, "ADRIANO_OIDC_AUTHORITY": authority})

    assert Settings().oidc_authority == authority


@pytest.mark.parametrize(
    "authority",
    [
        "ftp://idp.example.com",
        "idp.example.com",
        "https://idp.example.com/realms?x=1",
        "https://idp.example.com/#frag",
        "https://user:pw@idp.example.com",
        "https://idp.example.com/a b",
        "https://idp.example.com'; script-src *",
        'https://idp.example.com/"',
        "https://idp.example.com/\n",
    ],
)
def test_malformed_authority_fails_validation(
    monkeypatch: pytest.MonkeyPatch, authority: str
) -> None:
    """Ensure an authority with a query, credentials or quotes fails."""
    monkeypatch.setenv("ADRIANO_OIDC_AUTHORITY", authority)

    with pytest.raises(ValidationError, match="ADRIANO_OIDC_AUTHORITY"):
        Settings()


@pytest.mark.parametrize(
    "missing",
    [
        "ADRIANO_OIDC_CLIENT_ID",
        "ADRIANO_OIDC_CLIENT_SECRET",
        "ADRIANO_SESSION_KEY",
    ],
)
def test_oidc_needs_client_credentials_and_session_key(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """Ensure OIDC without the client secret or session key fails."""
    _set_env(monkeypatch, {k: v for k, v in OIDC_ENV.items() if k != missing})

    with pytest.raises(ValidationError, match=missing):
        Settings()


def test_complete_oidc_settings_are_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure a complete confidential-client configuration validates."""
    _set_env(monkeypatch, OIDC_ENV)

    settings = Settings()

    assert settings.oidc_client_secret is not None
    assert settings.oidc_client_secret.get_secret_value() == "s3cret"
    assert "s3cret" not in repr(settings)
    assert TEST_SESSION_KEY not in repr(settings)


def test_dev_auth_needs_a_session_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure enabling dev auth without a session key fails loudly."""
    monkeypatch.setenv("ADRIANO_DEV_AUTH_ENABLED", "true")

    with pytest.raises(ValidationError, match="ADRIANO_SESSION_KEY"):
        Settings()


def test_dev_auth_with_a_session_key_is_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure dev auth plus a session key validates."""
    monkeypatch.setenv("ADRIANO_DEV_AUTH_ENABLED", "true")
    monkeypatch.setenv("ADRIANO_SESSION_KEY", TEST_SESSION_KEY)

    assert Settings().dev_auth_enabled is True


@pytest.mark.parametrize(
    "key", ["not-a-key", "c2hvcnQ=", TEST_SESSION_KEY[:-2], "é" * 44]
)
def test_malformed_session_key_fails_validation(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    """Ensure a session key that is not a Fernet key is rejected."""
    monkeypatch.setenv("ADRIANO_SESSION_KEY", key)

    with pytest.raises(ValidationError, match="Fernet key"):
        Settings()


def test_session_defaults() -> None:
    """Ensure the session lifetimes and scope have their defaults."""
    settings = Settings()

    assert settings.session_idle_minutes == 480
    assert settings.session_max_hours == 24
    assert settings.session_key is None
    assert settings.oidc_scope == "openid profile email offline_access"


@pytest.mark.parametrize(
    "name", ["ADRIANO_SESSION_IDLE_MINUTES", "ADRIANO_SESSION_MAX_HOURS"]
)
def test_session_lifetimes_must_be_positive(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Ensure a zero session lifetime fails validation."""
    monkeypatch.setenv(name, "0")

    with pytest.raises(ValidationError):
        Settings()


def test_serving_defaults() -> None:
    """Ensure the image-facing settings have their documented defaults."""
    settings = Settings()

    assert settings.static_dir is None
    assert settings.migrate_on_start is True
    assert settings.version == "dev"
    assert settings.workers == 4
    assert settings.forwarded_allow_ips is None


def test_workers_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ADRIANO_WORKERS=0 fails validation."""
    monkeypatch.setenv("ADRIANO_WORKERS", "0")

    with pytest.raises(ValidationError, match="workers"):
        Settings()


def test_tls_verification_is_on_by_default() -> None:
    """Ensure outbound TLS certificates are verified unless disabled."""
    settings = Settings()

    assert settings.tls_verify is True


def test_tls_verification_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure ADRIANO_TLS_VERIFY=false turns verification off."""
    monkeypatch.setenv("ADRIANO_TLS_VERIFY", "false")

    settings = Settings()

    assert settings.tls_verify is False


def test_extra_ca_certs_are_unset_by_default() -> None:
    """Ensure no extra CA certificates are trusted unless configured."""
    settings = Settings()

    assert settings.extra_ca_certs is None


def test_extra_ca_certs_split_on_commas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ensure ADRIANO_EXTRA_CA_CERTS takes comma-separated paths."""
    bundle = tmp_path / "bundle.pem"
    bundle.touch()
    directory = tmp_path / "certs"
    directory.mkdir()
    monkeypatch.setenv("ADRIANO_EXTRA_CA_CERTS", f" {bundle} ,{directory},, ")

    settings = Settings()

    assert settings.extra_ca_certs == (bundle, directory)


def test_extra_ca_certs_reject_missing_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ensure a path that does not exist fails validation, named."""
    present = tmp_path / "ca.pem"
    present.touch()
    missing = tmp_path / "missing.pem"
    monkeypatch.setenv("ADRIANO_EXTRA_CA_CERTS", f"{present},{missing}")

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    message = excinfo.value.errors()[0]["msg"]
    assert "ADRIANO_EXTRA_CA_CERTS" in message
    assert str(missing) in message
    assert str(present) not in message
