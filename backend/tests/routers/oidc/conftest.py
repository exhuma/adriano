"""
Fixtures for the OIDC sign-in, refresh and sign-out router tests.

The identity provider is :class:`tests.auth_helpers.FakeIdp`:
discovery, token and revocation endpoints behind
``httpx.MockTransport``, injected by overriding the
``get_oidc_validator`` and ``get_idp_client`` dependencies. ``client``
is a client of an app with OIDC configured, not signed in.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.config import Settings
from tests.auth_helpers import ClientFactory, FakeIdp, client_factory
from tests.routers.oidc.support import OIDC


@pytest.fixture
def idp() -> FakeIdp:
    """
    Provide a fresh fake identity provider.

    :returns: The fake IdP.
    """
    return FakeIdp()


@pytest.fixture
def make_client(
    test_settings: Settings,
    catalog_file: Path,
    clean_engine: Engine,
    idp: FakeIdp,
) -> Iterator[ClientFactory]:
    """
    Build clients signing in at the fake IdP.

    :param test_settings: Base test settings.
    :param catalog_file: The router tests' ``catalog.yaml``.
    :param clean_engine: Truncated, migrated engine.
    :param idp: The fake IdP.
    :returns: A factory ``(csrf=True, **settings_updates) -> client``.
    """
    with client_factory(
        test_settings, catalog_file, defaults=OIDC, idp=idp
    ) as factory:
        yield factory


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    """
    Provide a client of an app with OIDC configured.

    :param make_client: Client factory.
    :returns: The client (not signed in).
    """
    return make_client()
