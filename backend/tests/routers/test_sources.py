"""Tests for ``GET /api/v1/sources`` (registration status and freshness)."""

import datetime

from fastapi.testclient import TestClient

from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.conftest import mark_poll_ok


def test_sources_report_configuration_and_freshness(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure each registration reports its config and a stale flag."""
    mark_poll_ok(provider, "central")

    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    by_id = {entry["id"]: entry for entry in response.json()}
    assert set(by_id) == {"central", "other"}
    central = by_id["central"]
    assert central["type"] == "filesystem"
    assert central["enabled"] is True
    assert central["config_error"] is None
    assert central["config_error_code"] is None
    assert central["intake"] == ["poll"]
    assert central["published_ref"] == "local"
    assert central["last_status"] == "ok"
    assert central["last_success_at"] is not None
    assert central["stale"] is False
    other = by_id["other"]
    assert other["last_status"] == "never"
    assert other["last_success_at"] is None
    assert other["stale"] is True


def test_a_failed_poll_is_always_stale(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure a failed last poll is stale even with a recent attempt."""
    from app.storage.port import PollStatus

    with provider.unit_of_work() as store:
        store.update_poll_status(
            "central", PollStatus.FAILED, datetime.datetime.now(datetime.UTC)
        )

    response = client.get("/api/v1/sources")

    central = next(e for e in response.json() if e["id"] == "central")
    assert central["last_status"] == "failed"
    assert central["stale"] is True


def test_an_old_success_is_stale(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure a success older than the threshold is reported as stale."""
    long_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=5)
    mark_poll_ok(provider, "central", when=long_ago)

    response = client.get("/api/v1/sources")

    central = next(e for e in response.json() if e["id"] == "central")
    assert central["last_status"] == "ok"
    assert central["stale"] is True
