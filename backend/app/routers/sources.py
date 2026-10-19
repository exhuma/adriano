"""
HTTP routes for source registration status and operator polls.

``GET /api/v1/sources`` (``read``) reports the configuration and
freshness of every registration; the ``stale`` flag uses
``ADRIANO_STALE_AFTER_MINUTES`` (see
:func:`app.services.catalog.is_stale`).

``POST /api/v1/sources/poll`` and ``POST /api/v1/sources/{id}/poll``
(``operate``) validate the request, then run the polling service in a
background worker thread and answer **202** with the accepted
registration ids. Unknown id: 404; disabled or push-only registration
(or nothing pollable at all): 409. Progress is visible through
``GET /api/v1/sources``. See :mod:`app.services.poll_trigger`.
"""

import datetime

from fastapi import APIRouter, BackgroundTasks, Depends

from app.auth.deps import Principal, require_permission
from app.auth.rbac import Permission
from app.catalog_config import CatalogConfig
from app.composition import (
    CatalogRuntime,
    build_polling_service,
    get_catalog_runtime,
    get_store_provider,
)
from app.config import Settings, get_settings
from app.domain.approval import principal as principal_key
from app.domain.frontmatter import JsonValue
from app.errors import ConfigurationError
from app.schemas.auth import PollAcceptedOut
from app.schemas.sources import SourceOut
from app.services import catalog
from app.services.poll_trigger import run_polls, select_poll_targets
from app.storage.port import CatalogStoreProvider

router = APIRouter(prefix="/api/v1", tags=["sources"])

_read = Depends(require_permission(Permission.READ))
_operate = require_permission(Permission.OPERATE)


@router.get("/sources", response_model=list[SourceOut], dependencies=[_read])
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


def _config(runtime: CatalogRuntime | None) -> CatalogConfig:
    """
    Return the loaded configuration.

    :param runtime: Startup state.
    :returns: The configuration.
    :raises ConfigurationError: If the lifespan did not run.
    """
    if runtime is None:
        raise ConfigurationError("catalog configuration is not loaded")
    return runtime.config


def _accept(
    source_id: str | None,
    principal: Principal,
    runtime: CatalogRuntime | None,
    provider: CatalogStoreProvider,
    background: BackgroundTasks,
) -> PollAcceptedOut:
    """
    Validate a poll request and schedule it in the background.

    :param source_id: One registration, or ``None`` for all.
    :param principal: The operator.
    :param runtime: Startup state.
    :param provider: Storage provider.
    :param background: Background task queue of the response.
    :returns: The accepted ids.
    """
    config = _config(runtime)
    targets = select_poll_targets(config, source_id)
    trigger: JsonValue = {
        "trigger": "api",
        "principal": principal_key(principal.issuer, principal.subject),
    }
    service = build_polling_service(provider, config)
    background.add_task(run_polls, service, targets, trigger)
    return PollAcceptedOut(
        accepted=targets,
        message=(
            f"poll started for {len(targets)} registration(s); "
            f"see GET /api/v1/sources for the outcome"
        ),
    )


@router.post("/sources/poll", status_code=202, response_model=PollAcceptedOut)
def poll_all_sources(
    background: BackgroundTasks,
    principal: Principal = Depends(_operate),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
    provider: CatalogStoreProvider = Depends(get_store_provider),
) -> PollAcceptedOut:
    """
    Poll every pollable registration in the background.

    :param background: Background task queue.
    :param principal: The operator (``operate`` permission).
    :param runtime: Startup state.
    :param provider: Storage provider (overridden by tests).
    :returns: The accepted ids (HTTP 202).
    :raises app.errors.ConflictError: If nothing is pollable.
    """
    return _accept(None, principal, runtime, provider, background)


@router.post(
    "/sources/{source_id}/poll",
    status_code=202,
    response_model=PollAcceptedOut,
)
def poll_one_source(
    source_id: str,
    background: BackgroundTasks,
    principal: Principal = Depends(_operate),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
    provider: CatalogStoreProvider = Depends(get_store_provider),
) -> PollAcceptedOut:
    """
    Poll one registration in the background.

    :param source_id: Registration id.
    :param background: Background task queue.
    :param principal: The operator (``operate`` permission).
    :param runtime: Startup state.
    :param provider: Storage provider (overridden by tests).
    :returns: The accepted id (HTTP 202).
    :raises app.errors.NotFoundError: If the id is not configured.
    :raises app.errors.ConflictError: If it cannot be polled.
    """
    return _accept(source_id, principal, runtime, provider, background)
