"""Tests for ``GET /api/v1/facets`` (source/project filter options)."""

import uuid

from fastapi.testclient import TestClient

from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.conftest import adr, seed


def test_facets_count_rows_per_source_and_project(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure facets group record counts by source then project."""
    with provider.lock_registration("central") as store:
        seed(
            store,
            source_id="central",
            project="platform",
            path="doc/decisions/2024-01-01-a.md",
            content=adr(uuid.uuid4(), title="A"),
        )
        seed(
            store,
            source_id="central",
            project="platform",
            path="doc/decisions/2024-01-02-b.md",
            content=adr(uuid.uuid4(), title="B"),
        )
        seed(
            store,
            source_id="central",
            project="payments",
            path="doc/decisions/2024-01-01-c.md",
            content=adr(uuid.uuid4(), title="C"),
        )
    with provider.lock_registration("other") as store:
        seed(
            store,
            source_id="other",
            project="payments",
            path="doc/decisions/2024-01-01-d.md",
            content=adr(uuid.uuid4(), title="D"),
        )

    response = client.get("/api/v1/facets")

    assert response.status_code == 200
    sources = {s["source_id"]: s for s in response.json()["sources"]}
    assert sources["central"]["count"] == 3
    central_projects = {
        p["project"]: p["count"] for p in sources["central"]["projects"]
    }
    assert central_projects == {"platform": 2, "payments": 1}
    assert sources["other"]["count"] == 1


def test_facets_are_empty_for_an_empty_catalog(client: TestClient) -> None:
    """Ensure an empty catalog reports no sources, not an error."""
    response = client.get("/api/v1/facets")

    assert response.status_code == 200
    assert response.json() == {"sources": []}
