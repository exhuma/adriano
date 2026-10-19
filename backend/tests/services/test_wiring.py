"""Tests for the startup sync (app lifespan) and the ``adriano`` CLI."""

import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.cli import main
from app.config import Settings, get_settings
from app.main import create_app
from app.storage.port import PollStatus
from app.storage.postgres.store import PostgresStoreProvider

EXAMPLE = Path(__file__).resolve().parents[3] / "catalog.example.yaml"
POLICY_ONLY = """
sources: []
approval_policy: {id: global, version: 1, reviewers: {roles: [r]}}
rbac: {roles: {admin: [read, operate]}}
"""


def with_config(settings: Settings, path: Path) -> Settings:
    """
    Point settings at a configuration file.

    :param settings: Test settings.
    :param path: Configuration file.
    :returns: Updated settings.
    """
    return settings.model_copy(update={"config_file": str(path)})


def test_startup_syncs_registrations_and_reports_health(
    test_settings: Settings, provider: PostgresStoreProvider
) -> None:
    """Ensure the lifespan syncs registrations and /healthz reports it."""
    app = create_app()
    settings = with_config(test_settings, EXAMPLE)
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        body = client.get("/healthz").json()

    assert body["status"] == "ok"
    assert body["config"] == "ok"
    assert body["policy"] == "configured"
    assert body["registrations"] == "synced"
    with provider.unit_of_work() as store:
        rows = {r.id: r for r in store.list_registrations()}
    assert rows["central"].enabled is False
    assert "not available yet" in (rows["central"].config_error or "")
    assert rows["central"].last_status is PollStatus.DISABLED
    assert rows["other"].enabled is False  # seeded, not in the file


def test_startup_survives_a_broken_configuration(
    tmp_path: Path, test_settings: Settings
) -> None:
    """Ensure an unparseable catalog.yaml does not prevent startup."""
    path = tmp_path / "catalog.yaml"
    path.write_text("sources: [", encoding="utf-8")
    app = create_app()
    settings = with_config(test_settings, path)
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["config"] == "invalid"
    assert response.json()["policy"] == "invalid"
    assert response.json()["registrations"] == "skipped"


def test_check_config_exit_codes(
    tmp_path: Path, test_settings: Settings
) -> None:
    """Ensure check-config prints problems and exits non-zero on errors."""
    valid = tmp_path / "catalog.yaml"
    valid.write_text(POLICY_ONLY, encoding="utf-8")
    out = io.StringIO()

    failing = main(
        ["check-config"], settings=with_config(test_settings, EXAMPLE), out=out
    )
    passing = main(
        ["check-config"],
        settings=with_config(test_settings, valid),
        out=io.StringIO(),
    )

    assert failing == 1
    assert "central [filesystem] DISABLED" in out.getvalue()
    assert "Approval policy: configured" in out.getvalue()
    assert passing == 0


def test_poll_command_handles_nothing_to_poll_and_unknown_ids(
    test_settings: Settings, provider: PostgresStoreProvider
) -> None:
    """Ensure poll syncs, reports nothing to poll, and rejects bad ids."""
    settings = with_config(test_settings, EXAMPLE)
    out = io.StringIO()

    nothing = main(["poll"], settings=settings, out=out)
    unknown = main(["poll", "--source", "nope"], settings=settings)
    disabled = main(
        ["poll", "--source", "central"], settings=settings, out=io.StringIO()
    )

    assert nothing == 0
    assert "nothing to poll" in out.getvalue()
    assert unknown == 2
    assert disabled == 1
    with provider.unit_of_work() as store:
        assert store.get_registration("gitlab-platform") is not None
