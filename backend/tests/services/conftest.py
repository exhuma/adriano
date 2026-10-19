"""
Fixtures for the service and wiring (lifespan, CLI) integration tests.

Reuses the migrated test database fixtures of the storage tests.
"""

from tests.storage.conftest import (  # noqa: F401
    engine,
    migrated_engine,
    provider,
)
