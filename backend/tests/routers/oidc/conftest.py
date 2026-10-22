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
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.auth.deps import get_idp_client, get_oidc_validator
from app.config import Settings, get_settings
from app.main import create_app
from tests.auth_helpers import FakeIdp, https_client
from tests.routers.oidc.support import OIDC, ClientFactory


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
    :returns: A factory ``(**settings_updates) -> client``.
    """
    stack: list[TestClient] = []

    def _make(**updates: Any) -> TestClient:
        settings = test_settings.model_copy(
            update={"config_file": str(catalog_file), **OIDC, **updates}
        )
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        if settings.oidc_authority is not None:
            validator = idp.validator(issuer=settings.oidc_issuer)
            client = idp.idp_client(validator)
            app.dependency_overrides[get_oidc_validator] = lambda: validator
            app.dependency_overrides[get_idp_client] = lambda: client
        test_client = https_client(app)
        test_client.__enter__()
        stack.append(test_client)
        return test_client

    yield _make
    for test_client in stack:
        test_client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    """
    Provide a client of an app with OIDC configured.

    :param make_client: Client factory.
    :returns: The client (not signed in).
    """
    return make_client()
