"""Integration tests for the per-registration advisory lock."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import OperationalError

from app.database import _make_engine_url
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import database_url_for_tests


@pytest.fixture
def impatient(engine: Engine) -> Iterator[PostgresStoreProvider]:
    """
    Build a second provider whose lock waits time out after 200 ms.

    :param engine: Clean engine (ensures the schema exists).
    :returns: A provider on a separate engine.
    """
    other = create_engine(
        _make_engine_url(database_url_for_tests()),
        connect_args={"options": "-c lock_timeout=200"},
    )
    yield PostgresStoreProvider(other)
    other.dispose()


def test_lock_blocks_same_registration_only(
    provider: PostgresStoreProvider, impatient: PostgresStoreProvider
) -> None:
    """Ensure the lock excludes other workers for its registration only."""
    with provider.lock_registration("central") as store:
        store.list_registrations()
        with pytest.raises(OperationalError, match="lock timeout"):
            with impatient.lock_registration("central"):
                pass  # pragma: no cover - the lock must not be granted
        with impatient.lock_registration("other") as other:
            assert other.get_registration("other") is not None
    with impatient.lock_registration("central") as again:
        assert again.get_registration("central") is not None


def test_lock_is_released_on_rollback(
    provider: PostgresStoreProvider, impatient: PostgresStoreProvider
) -> None:
    """Ensure an error inside the locked unit of work frees the lock."""
    with pytest.raises(RuntimeError):
        with provider.lock_registration("central"):
            raise RuntimeError("boom")
    with impatient.lock_registration("central") as store:
        assert store.get_registration("central") is not None
