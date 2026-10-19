"""Integration tests for source registrations in the PostgreSQL store."""

import datetime

import pytest

from app.storage.port import PollStatus, RegistrationConfig
from app.storage.postgres.registrations import REMOVED_FROM_CONFIG
from app.storage.postgres.store import PostgresStoreProvider

T0 = datetime.datetime(2026, 10, 19, 12, 0, tzinfo=datetime.UTC)


def test_sync_inserts_updates_and_disables(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure sync upserts listed entries and disables removed ones."""
    with provider.unit_of_work() as store:
        store.sync_registrations(
            [
                RegistrationConfig(
                    id="central", type="filesystem", config={"root": "/x"}
                ),
                RegistrationConfig(
                    id="broken",
                    type="gitlab",
                    config={},
                    enabled=False,
                    config_error="base_url missing",
                ),
            ]
        )
    with provider.unit_of_work() as store:
        regs = {reg.id: reg for reg in store.list_registrations()}
    assert sorted(regs) == ["broken", "central", "other"]
    assert regs["central"].config == {"root": "/x"}
    assert regs["central"].last_status is PollStatus.NEVER
    assert regs["broken"].enabled is False
    assert regs["broken"].last_status is PollStatus.DISABLED
    assert regs["broken"].config_error == "base_url missing"
    assert regs["other"].enabled is False
    assert regs["other"].config_error == REMOVED_FROM_CONFIG


def test_reenabled_registration_restarts_at_never(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure a disabled registration that becomes valid is 'never'."""
    with provider.unit_of_work() as store:
        store.sync_registrations([])
        store.sync_registrations(
            [RegistrationConfig(id="other", type="filesystem", config={})]
        )
        reg = store.get_registration("other")
    assert reg is not None
    assert reg.enabled is True
    assert reg.config_error is None
    assert reg.last_status is PollStatus.NEVER


def test_poll_status_tracks_success_only_for_ok(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure last_success_at moves only on an ok poll."""
    later = T0 + datetime.timedelta(hours=1)
    with provider.unit_of_work() as store:
        store.update_poll_status("central", PollStatus.OK, T0)
        store.update_poll_status(
            "central", PollStatus.FAILED, later, {"message": "boom"}
        )
        reg = store.get_registration("central")
    assert reg is not None
    assert reg.last_status is PollStatus.FAILED
    assert reg.last_attempt_at == later
    assert reg.last_success_at == T0
    assert reg.last_error == {"message": "boom"}


def test_poll_status_unknown_registration(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure updating an unknown registration raises LookupError."""
    with provider.unit_of_work() as store, pytest.raises(LookupError):
        store.update_poll_status("nope", PollStatus.OK, T0)
