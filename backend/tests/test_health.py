"""Tests for the ``GET /healthz`` route."""

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app


def test_healthz_reports_ok_when_database_is_reachable(
    client: TestClient,
) -> None:
    """Ensure /healthz returns 200 and status ok with a live database."""
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_healthz_reports_degraded_with_an_unreachable_database(
    test_settings: Settings,
) -> None:
    """Ensure /healthz returns 503 when the database is unreachable."""
    broken_settings = test_settings.model_copy(
        update={
            "database_url": "postgresql://adriano:adriano@localhost:1/adriano"
        }
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: broken_settings

    with TestClient(app) as broken_client:
        response = broken_client.get("/healthz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "database": "unavailable",
    }
