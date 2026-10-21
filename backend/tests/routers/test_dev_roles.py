"""
Tests for the dev-only ``GET /auth/dev/roles`` (dev sign-in presets).

Real HTTP through the app (its lifespan syncs registrations into the
test database). Each test writes its own ``catalog.yaml`` so both the
local example shape (``admin``/``adr-reader``) and the demo shape
(``reader``/``admin``/``adr-reviewer``) are covered.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.main import create_app

type ClientFactory = Callable[..., TestClient]

#: Shape of the repository's local ``catalog.yaml``.
LOCAL_CATALOG = """
approval_policy:
  id: global
  version: 1
  required: true
  reviewers:
    users: ["https://idp.example.com|subject-123"]
    roles: [adr-reviewer]
rbac:
  roles:
    admin: [read, operate]
    adr-reader: [read]
"""

#: Shape of ``catalog.demo.yaml``.
DEMO_CATALOG = """
approval_policy:
  id: global
  version: 1
  required: true
  reviewers:
    users: []
    roles: [adr-reviewer]
rbac:
  roles:
    admin: [read, operate]
    adr-reviewer: [read]
    reader: [read]
"""

#: No approval policy at all.
NO_POLICY_CATALOG = """
rbac:
  roles:
    adr-reader: [read]
"""


@pytest.fixture
def make_client(
    test_settings: Settings, tmp_path: Path, clean_engine: Engine
) -> Iterator[ClientFactory]:
    """
    Build clients for a given ``catalog.yaml`` text and settings.

    :param test_settings: Base test settings (dev auth enabled).
    :param tmp_path: Pytest temporary directory.
    :param clean_engine: Truncated, migrated engine.
    :returns: A factory ``(catalog_text, **settings_updates) -> client``.
    """
    stack: list[TestClient] = []

    def _make(catalog_text: str, **updates: Any) -> TestClient:
        path = tmp_path / "catalog.yaml"
        path.write_text(catalog_text, encoding="utf-8")
        settings = test_settings.model_copy(
            update={"config_file": str(path), **updates}
        )
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        client = TestClient(app)
        client.__enter__()
        stack.append(client)
        return client

    yield _make
    for client in stack:
        client.__exit__(None, None, None)


def test_roles_route_is_absent_when_dev_auth_is_off(
    make_client: ClientFactory,
) -> None:
    """Ensure /auth/dev/roles is a plain 404 with dev auth disabled."""
    client = make_client(LOCAL_CATALOG, dev_auth_enabled=False)

    response = client.get("/auth/dev/roles")

    assert response.status_code == 404


def test_roles_route_is_absent_without_the_secret(
    make_client: ClientFactory,
) -> None:
    """Ensure /auth/dev/roles is not mounted without a shared secret."""
    client = make_client(
        LOCAL_CATALOG,
        dev_auth_enabled=True,
        dev_shared_secret=None,
        oidc_authority="https://idp.test/realms/adr",
    )

    response = client.get("/auth/dev/roles")

    assert response.status_code == 404


def test_roles_of_the_local_catalog_shape(
    make_client: ClientFactory,
) -> None:
    """Ensure rbac roles and reviewer roles (not users) are listed."""
    client = make_client(LOCAL_CATALOG)

    response = client.get("/auth/dev/roles")

    assert response.status_code == 200
    assert response.json() == {
        "roles": [
            {"name": "admin", "permissions": ["operate", "read"]},
            {"name": "adr-reader", "permissions": ["read"]},
        ],
        "reviewer_roles": ["adr-reviewer"],
    }


def test_roles_of_the_demo_catalog_shape(
    make_client: ClientFactory,
) -> None:
    """Ensure a reviewer role that is also an rbac role is listed twice."""
    client = make_client(DEMO_CATALOG)

    body = client.get("/auth/dev/roles").json()

    assert body == {
        "roles": [
            {"name": "admin", "permissions": ["operate", "read"]},
            {"name": "adr-reviewer", "permissions": ["read"]},
            {"name": "reader", "permissions": ["read"]},
        ],
        "reviewer_roles": ["adr-reviewer"],
    }


def test_roles_without_a_policy_have_no_reviewer_roles(
    make_client: ClientFactory,
) -> None:
    """Ensure a missing approval policy yields no reviewer roles."""
    client = make_client(NO_POLICY_CATALOG)

    body = client.get("/auth/dev/roles").json()

    assert body == {
        "roles": [{"name": "adr-reader", "permissions": ["read"]}],
        "reviewer_roles": [],
    }


def test_roles_route_needs_no_token(make_client: ClientFactory) -> None:
    """Ensure the dev dialog can list roles before anyone signs in."""
    client = make_client(LOCAL_CATALOG)

    response = client.get(
        "/auth/dev/roles", headers={"Authorization": "Bearer junk"}
    )

    assert response.status_code == 200
