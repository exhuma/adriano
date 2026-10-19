"""
HTTP route for source registration status.

Reports the configuration and freshness of every registration; the
``stale`` flag uses ``ADRIANO_STALE_AFTER_MINUTES`` (see
:func:`app.services.catalog.is_stale`). Operator-triggered polling
(``POST /api/v1/sources/poll``) arrives with phase 06 authorization.
"""

import datetime

from fastapi import APIRouter, Depends

from app.composition import (
    CatalogRuntime,
    get_catalog_runtime,
    get_store_provider,
)
from app.config import Settings, get_settings
from app.schemas.sources import SourceOut
from app.services import catalog
from app.storage.port import CatalogStoreProvider

router = APIRouter(prefix="/api/v1", tags=["sources"])


@router.get("/sources", response_model=list[SourceOut])
def list_sources(
    provider: CatalogStoreProvider = Depends(get_store_provider),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
    settings: Settings = Depends(get_settings),
) -> list[SourceOut]:
    """
    List every stored source registration.

    :param provider: Storage provider (overridden by tests).
    :param runtime: Startup configuration state.
    :param settings: Application settings (for the stale threshold).
    :returns: One entry per stored registration, ordered by id.
    """
    config_sources = runtime.config.sources if runtime is not None else ()
    with provider.unit_of_work() as store:
        summaries = catalog.list_sources(
            store,
            config_sources,
            now=datetime.datetime.now(datetime.UTC),
            stale_after_minutes=settings.stale_after_minutes,
        )
    return [SourceOut.model_validate(summary) for summary in summaries]
