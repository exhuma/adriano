"""Shared pytest fixtures for the adriano backend test suite.

Tests always run against ``ADRIANO_TEST_DATABASE_URL``, never against
the development database, so the dependency-overridden settings
object for the FastAPI test client always point at the test
database.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Build settings pointed at the test database.

    The configuration file points at a path that does not exist, so the
    app lifespan never syncs a developer's ``catalog.yaml`` into the
    test database.

    :returns: A :class:`Settings` instance whose ``database_url`` is
        read from ``ADRIANO_TEST_DATABASE_URL``.
    """
    settings = Settings()
    return settings.model_copy(
        update={
            "database_url": settings.test_database_url,
            "config_file": str(Path(__file__).parent / "no-catalog.yaml"),
        }
    )


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    """Build a test client wired to the test database.

    :param test_settings: Settings pointed at the test database.
    :returns: A :class:`~fastapi.testclient.TestClient` for the app.
    """
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
