"""
Sync configured source registrations into storage.

Run at application startup and by the CLI before polling. Configured
registrations are inserted or updated (invalid ones disabled with their
``config_error``); stored registrations no longer configured are
disabled, never deleted (see
:meth:`app.storage.port.CatalogStore.sync_registrations`).

The sync only runs when the configuration file was read and parsed: a
missing or unparseable file is a deployment problem that must not
disable every registration as a side effect.

Public API: :func:`sync_registrations`.
"""

from app.catalog_config import CatalogConfig, ConfigFileStatus
from app.storage.port import CatalogStoreProvider


def sync_registrations(
    provider: CatalogStoreProvider, config: CatalogConfig
) -> bool:
    """
    Make stored registrations match the configuration.

    :param provider: Storage provider.
    :param config: Loaded configuration.
    :returns: ``True`` if synced, ``False`` if skipped because the file
        could not be loaded.
    """
    if config.file_status is not ConfigFileStatus.OK:
        return False
    with provider.unit_of_work() as store:
        store.sync_registrations(config.registration_configs())
    return True
