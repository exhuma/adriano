"""Shared pytest fixtures for the adriano backend test suite.

Tests always run against ``ADRIANO_TEST_DATABASE_URL``, never against
the development database, so the dependency-overridden settings
object for the FastAPI test client always point at the test
database.

Auth: test settings never use OIDC (no IdP calls) and enable the
dev-only HS256 path with :data:`tests.auth_helpers.TEST_DEV_SECRET`, a
throwaway value that exists only in the test suite.

``ADRIANO_DATABASE_URL`` is required by the settings and ``app.main``
builds the application at import time, so it defaults to the test
database DSN here, before any ``app`` import.
"""

import os
from collections.abc import Iterator
from pathlib import Path

os.environ.setdefault(
    "ADRIANO_DATABASE_URL",
    os.environ.get(
        "ADRIANO_TEST_DATABASE_URL",
        "postgresql://adriano:adriano@localhost:55432/adriano_test",
    ),
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.auth_helpers import TEST_DEV_SECRET  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_source_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Remove source secret env vars a developer may have exported.

    Tests that read ``os.environ`` (via the composition root) must not
    depend on the developer's shell, e.g. an exported GitLab token.
    """
    for name in list(os.environ):
        if name.startswith(("ADRIANO_GITLAB_TOKEN", "ADRIANO_PUSH_TOKEN")):
            monkeypatch.delenv(name)


@pytest.fixture
def test_settings() -> Settings:
    """Build settings pointed at the test database.

    The configuration file points at a path that does not exist, so the
    app lifespan never syncs a developer's ``catalog.yaml`` into the
    test database. Auth settings are pinned (whatever the developer's
    environment says): no OIDC, dev auth enabled with the test secret.

    :returns: A :class:`Settings` instance whose ``database_url`` is
        read from ``ADRIANO_TEST_DATABASE_URL``.
    """
    settings = Settings()
    return settings.model_copy(
        update={
            "database_url": settings.test_database_url,
            "config_file": str(Path(__file__).parent / "no-catalog.yaml"),
            "oidc_authority": None,
            "oidc_issuer": None,
            "oidc_audience": "adr_viewer",
            "oidc_roles_claim": "roles",
            "dev_auth_enabled": True,
            "dev_shared_secret": TEST_DEV_SECRET,
        }
    )


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    """Build a test client wired to the test database.

    :param test_settings: Settings pointed at the test database.
    :returns: A :class:`~fastapi.testclient.TestClient` for the app.
    """
    app = create_app(test_settings)
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
