"""Health-check route used by deployment and container probes.

``GET /healthz`` reports whether the application can reach its
database (``status`` / ``database``; HTTP 503 when unreachable) plus the
configuration state loaded at startup: ``config`` (file ``ok``,
``missing`` or ``invalid``), ``policy`` (``configured``, ``missing`` or
``invalid``) and ``registrations`` (startup sync ``synced``, ``skipped``
or ``failed``). Configuration problems never make the probe fail:
restarting the container would not fix them.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.composition import CatalogRuntime, get_catalog_runtime
from app.database import get_db

router = APIRouter()

_UNKNOWN = "unknown"


def _config_status(runtime: CatalogRuntime | None) -> dict[str, str]:
    """
    Summarise the startup configuration state.

    :param runtime: Startup state, ``None`` if the lifespan did not run.
    :returns: ``config``, ``policy`` and ``registrations`` keys.
    """
    if runtime is None:
        return {
            "config": _UNKNOWN,
            "policy": _UNKNOWN,
            "registrations": _UNKNOWN,
        }
    return {
        "config": runtime.config.file_status.value,
        "policy": runtime.config.policy.status.value,
        "registrations": runtime.sync.value,
    }


@router.get("/healthz")
def healthz(
    response: Response,
    db: Session = Depends(get_db),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
) -> dict[str, str]:
    """Report application, database and configuration health.

    Returns HTTP 200 with ``status: ok`` when the database is
    reachable, or HTTP 503 with ``status: degraded`` otherwise. The
    ``config``, ``policy`` and ``registrations`` keys report the
    configuration loaded at startup.

    :param response: Outgoing response, used to set the status code.
    :param db: Request-scoped database session.
    :param runtime: Startup state of the catalog.
    :returns: A mapping with ``status``, ``database``, ``config``,
        ``policy`` and ``registrations`` keys.
    """
    details = _config_status(runtime)
    try:
        db.execute(text("SELECT 1"))
    except OperationalError:
        response.status_code = 503
        return {"status": "degraded", "database": "unavailable", **details}
    return {"status": "ok", "database": "ok", **details}
