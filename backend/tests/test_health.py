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
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["config"] == "missing"
    assert body["policy"] == "missing"
    assert body["registrations"] == "skipped"


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
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"


def test_healthz_and_openapi_report_the_version(
    test_settings: Settings,
) -> None:
    """Ensure /healthz and the OpenAPI info carry ADRIANO_VERSION."""
    settings = test_settings.model_copy(update={"version": "2026.10.21"})
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as versioned_client:
        health = versioned_client.get("/healthz").json()
        schema = versioned_client.get("/openapi.json").json()

    assert health["version"] == "2026.10.21"
    assert schema["info"]["version"] == "2026.10.21"
