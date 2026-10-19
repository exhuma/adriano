"""
Tests for :class:`app.config.Settings` environment parsing.

Settings are built from an empty working directory so a developer's
``.env`` never leaks into the assertions.
"""

from pathlib import Path

import pytest

from app.config import Settings
from tests.auth_helpers import IDP_ISSUER, FakeIdp

BLANK_OPTIONAL = [
    "ADRIANO_OIDC_AUTHORITY",
    "ADRIANO_OIDC_ISSUER",
    "ADRIANO_DEV_SHARED_SECRET",
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
