"""
Fixtures for the session router tests.

``make_client`` builds https clients of apps with custom auth settings
(dev auth enabled by default), against the truncated test database.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.main import create_app
from tests.auth_helpers import https_client
from tests.routers.sessions.support import ClientFactory


@pytest.fixture
def make_client(
    test_settings: Settings, catalog_file: Path, clean_engine: Engine
) -> Iterator[ClientFactory]:
    """
    Build clients with custom auth settings.

    :param test_settings: Base test settings.
    :param catalog_file: The router tests' ``catalog.yaml``.
    :param clean_engine: Truncated, migrated engine.
    :returns: A factory ``(csrf=True, **settings_updates) -> client``.
    """
    stack: list[TestClient] = []

    def _make(*, csrf: bool = True, **updates: Any) -> TestClient:
        settings = test_settings.model_copy(
            update={"config_file": str(catalog_file), **updates}
        )
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        client = https_client(app, csrf=csrf)
        client.__enter__()
        stack.append(client)
        return client

    yield _make
    for client in stack:
        client.__exit__(None, None, None)
