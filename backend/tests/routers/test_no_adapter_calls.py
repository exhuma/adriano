"""
Ensure normal browse/search requests never construct a source adapter.

``phases/DECISIONS.md`` ("HTTP API") requires that read routes use only
the storage port; :func:`app.composition.default_registry` is the only
place a source type's adapter factory is built (binding
``SourceBinding.open_adapter``), and it is called exactly once, by
:func:`app.composition.load_catalog` during application startup. By
patching it to raise *after* the test client's lifespan already ran,
any read route that still touched it would fail loudly.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.conftest import adr, seed


def _never_call_the_registry() -> None:
    """Fail the test if a read route builds a source type registry."""
    raise AssertionError(
        "a read route must never construct a source type registry/adapter"
    )


def test_every_read_route_works_with_a_raising_source_registry(
    client: TestClient,
    provider: PostgresStoreProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure records/sources/facets routes succeed without the registry."""
    with provider.lock_registration("central") as store:
        record_id = seed(store, content=adr(uuid.uuid4(), title="Readable"))
    monkeypatch.setattr(
        "app.composition.default_registry", _never_call_the_registry
    )

    search = client.get("/api/v1/records")
    detail = client.get(f"/api/v1/records/{record_id}")
    sources = client.get("/api/v1/sources")
    facets = client.get("/api/v1/facets")
    missing = client.get(f"/api/v1/records/{uuid.uuid4()}")

    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["metadata"]["title"] == "Readable"
    assert sources.status_code == 200
    assert facets.status_code == 200
    assert missing.status_code == 404
