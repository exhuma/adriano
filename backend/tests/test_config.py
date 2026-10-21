"""
Tests for :class:`app.config.Settings` environment parsing.

Settings are built from an empty working directory so a developer's
``.env`` never leaks into the assertions.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings
from tests.auth_helpers import IDP_ISSUER, FakeIdp

BLANK_OPTIONAL = [
    "ADRIANO_OIDC_AUTHORITY",
    "ADRIANO_OIDC_ISSUER",
    "ADRIANO_OIDC_CLIENT_ID",
    "ADRIANO_OIDC_REDIRECT_URI",
    "ADRIANO_OIDC_POST_LOGOUT_REDIRECT_URI",
    "ADRIANO_DEV_SHARED_SECRET",
    "ADRIANO_STATIC_DIR",
    "ADRIANO_FORWARDED_ALLOW_IPS",
]


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
    monkeypatch.setenv("ADRIANO_OIDC_AUTHORITY", IDP_ISSUER)
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
    monkeypatch.setenv("ADRIANO_OIDC_AUTHORITY", authority)

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
    """Ensure an authority that could inject into the CSP is rejected."""
    monkeypatch.setenv("ADRIANO_OIDC_AUTHORITY", authority)

    with pytest.raises(ValidationError, match="ADRIANO_OIDC_AUTHORITY"):
        Settings()


def test_oidc_origin_drops_the_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the CSP origin is scheme://host[:port] of the authority."""
    monkeypatch.setenv("ADRIANO_OIDC_AUTHORITY", "https://idp.test:8443/r/a")

    assert Settings().oidc_origin == "https://idp.test:8443"


@pytest.mark.parametrize(
    ("name", "missing"),
    [
        ("ADRIANO_OIDC_AUTHORITY", "https://idp.example.com"),
        ("ADRIANO_OIDC_CLIENT_ID", "adriano-spa"),
    ],
)
def test_spa_needs_authority_and_client_id_together(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, missing: str
) -> None:
    """Ensure serving the SPA with half an OIDC client config fails."""
    monkeypatch.setenv("ADRIANO_STATIC_DIR", str(tmp_path))
    monkeypatch.setenv(name, missing)

    with pytest.raises(ValidationError, match="must be set together"):
        Settings()


def test_api_only_allows_an_authority_without_client_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure the pairing rule applies only when the SPA is served."""
    monkeypatch.setenv("ADRIANO_OIDC_AUTHORITY", "https://idp.example.com")

    assert Settings().oidc_client_id is None


def test_spa_settings_with_both_oidc_values_are_valid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ensure a complete SPA configuration validates."""
    monkeypatch.setenv("ADRIANO_STATIC_DIR", str(tmp_path))
    monkeypatch.setenv("ADRIANO_OIDC_AUTHORITY", "https://idp.example.com")
    monkeypatch.setenv("ADRIANO_OIDC_CLIENT_ID", "adriano-spa")

    settings = Settings()

    assert settings.static_dir == tmp_path


def test_serving_defaults() -> None:
    """Ensure the image-facing settings have their documented defaults."""
    settings = Settings()

    assert settings.static_dir is None
    assert settings.migrate_on_start is True
    assert settings.version == "dev"
    assert settings.workers == 4
    assert settings.forwarded_allow_ips is None
    assert settings.oidc_scope == "openid profile email"


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
