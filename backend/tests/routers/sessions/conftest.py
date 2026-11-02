"""
Fixtures for the session router tests.

``make_client`` builds https clients of apps with custom auth settings
(dev auth enabled by default), against the truncated test database.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from app.config import Settings
from tests.auth_helpers import ClientFactory, client_factory


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
    with client_factory(test_settings, catalog_file) as factory:
        yield factory
