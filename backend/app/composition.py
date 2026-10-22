"""
Composition root: wires settings, configuration, storage and services.

This is the only module that names concrete implementations (the
PostgreSQL store, the default source type registry) and the only place
that hands the process environment to the configuration loader, which
resolves secrets referenced by env var **name** in ``catalog.yaml``.
Both the FastAPI lifespan (:mod:`app.main`) and the CLI
(:mod:`app.cli`) build their object graph here.

:class:`CatalogRuntime` is the startup state kept on ``app.state`` and
read by routes through :func:`get_catalog_runtime`. Read routes get
their storage provider through the :func:`get_store_provider`
dependency, which tests override with a provider bound to the test
database, exactly like :func:`app.config.get_settings`.

Public API: :class:`SyncStatus`, :class:`CatalogRuntime`,
:func:`load_catalog`, :func:`build_store_provider`,
:func:`build_polling_service`, :func:`start_catalog`,
:func:`log_problems`, :func:`get_catalog_runtime`,
:func:`get_store_provider`.
"""

import logging
import os
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Depends, Request
from sqlalchemy.exc import SQLAlchemyError

from app.catalog_config import CatalogConfig, load_catalog_config
from app.config import Settings, get_settings
from app.database import get_engine
from app.domain.issues import Severity
from app.services.polling import PollingService
from app.services.registrations import sync_registrations
from app.sources.registry import default_registry
from app.storage.port import CatalogStoreProvider
from app.storage.postgres.store import PostgresStoreProvider

logger = logging.getLogger(__name__)


class SyncStatus(StrEnum):
    """Outcome of the startup registration sync."""

    SYNCED = "synced"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CatalogRuntime:
    """
    Startup state of the catalog.

    :param config: Loaded configuration.
    :param sync: Outcome of the registration sync.
    """

    config: CatalogConfig
    sync: SyncStatus


def load_catalog(settings: Settings) -> CatalogConfig:
    """
    Load ``catalog.yaml`` with the default source types.

    :param settings: Application settings.
    :returns: The configuration (never raises for bad content).
    """
    if not settings.tls_verify:
        logger.warning(
            "ADRIANO_TLS_VERIFY is false: certificates of network "
            "sources (such as GitLab) are NOT verified. Never use this "
            "in production."
        )
    return load_catalog_config(
        settings.config_file,
        env=os.environ,
        registry=default_registry(tls_verify=settings.tls_verify),
    )


def build_store_provider(settings: Settings) -> CatalogStoreProvider:
    """
    Build the storage provider for the configured database.

    :param settings: Application settings.
    :returns: The provider.
    """
    return PostgresStoreProvider(get_engine(str(settings.database_url)))


def build_polling_service(
    provider: CatalogStoreProvider, config: CatalogConfig
) -> PollingService:
    """
    Build the polling service.

    :param provider: Storage provider.
    :param config: Loaded configuration.
    :returns: The service.
    """
    return PollingService(provider, config.sources)


def log_problems(config: CatalogConfig) -> None:
    """
    Log every configuration problem (messages are secret-free).

    :param config: Loaded configuration.
    """
    for problem in config.problems:
        level = (
            logging.ERROR
            if problem.severity is Severity.ERROR
            else logging.WARNING
        )
        logger.log(
            level, "catalog config %s: %s", problem.location, problem.message
        )


def start_catalog(settings: Settings) -> CatalogRuntime:
    """
    Load the configuration and sync registrations; never fails startup.

    :param settings: Application settings.
    :returns: The runtime state.
    """
    config = load_catalog(settings)
    log_problems(config)
    try:
        synced = sync_registrations(build_store_provider(settings), config)
    except SQLAlchemyError as exc:
        logger.warning(
            "source registrations not synced: database error %s",
            type(exc).__name__,
        )
        return CatalogRuntime(config, SyncStatus.FAILED)
    return CatalogRuntime(
        config, SyncStatus.SYNCED if synced else SyncStatus.SKIPPED
    )


def get_catalog_runtime(request: Request) -> CatalogRuntime | None:
    """
    FastAPI dependency: the startup state, if the lifespan ran.

    :param request: Current request.
    :returns: The runtime state, or ``None``.
    """
    return getattr(request.app.state, "catalog", None)


def get_store_provider(
    settings: Settings = Depends(get_settings),
) -> CatalogStoreProvider:
    """
    FastAPI dependency: the storage provider for the configured database.

    Routers depend on this (never on a concrete store implementation),
    so tests can override it -- or override :func:`app.config.get_settings`
    to point it at the test database, as every other test already does.

    :param settings: Application settings, injected for overriding.
    :returns: The provider.
    """
    return build_store_provider(settings)
