"""
Fixtures for the push intake, decision, diff and lifecycle tests.

Overrides the router tests' ``catalog_file`` with
:func:`tests.routers.approval.support.catalog_yaml` (a real filesystem
root in ``tmp_path``), exports the push tokens for every test, and
offers ``make_client`` for extra app instances with another policy.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app
from tests.auth_helpers import https_client, sign_in
from tests.routers.approval.support import (
    ClientFactory,
    catalog_yaml,
    set_push_tokens,
)


@pytest.fixture(autouse=True)
def push_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Export the test push tokens before any client starts.

    :param monkeypatch: Pytest monkeypatch.
    """
    set_push_tokens(monkeypatch)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """
    Create the shared filesystem root.

    :param tmp_path: Pytest temporary directory.
    :returns: The root directory.
    """
    path = tmp_path / "root"
    path.mkdir()
    return path


@pytest.fixture
def catalog_file(tmp_path: Path, root: Path) -> Path:
    """
    Write the decision test catalog.

    :param tmp_path: Pytest temporary directory.
    :param root: Filesystem root.
    :returns: The file path.
    """
    path = tmp_path / "catalog.yaml"
    path.write_text(catalog_yaml(root), encoding="utf-8")
    return path


@pytest.fixture
def make_client(
    tmp_path: Path, root: Path, router_settings: Settings
) -> Iterator[ClientFactory]:
    """
    Build extra clients with another ``approval_policy`` section.

    :param tmp_path: Pytest temporary directory.
    :param root: Filesystem root.
    :param router_settings: Base settings.
    :returns: ``make_client(policy_text_or_None)``, authenticated as an
        admin.
    """
    clients: list[TestClient] = []

    def _make(policy: str | None) -> TestClient:
        path = tmp_path / f"catalog-{len(clients)}.yaml"
        path.write_text(catalog_yaml(root, policy), encoding="utf-8")
        settings = router_settings.model_copy(update={"config_file": str(path)})
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        test_client = https_client(app)
        test_client.__enter__()
        sign_in(test_client, roles=["admin"])
        clients.append(test_client)
        return test_client

    yield _make
    for test_client in clients:
        test_client.__exit__(None, None, None)
