"""Health-check route used by deployment and container probes.

``GET /healthz`` reports whether the application can reach its
database (``status`` / ``database``; HTTP 503 when unreachable) plus the
configuration state loaded at startup: ``config`` (file ``ok``,
``missing`` or ``invalid``), ``policy`` (``configured``, ``missing`` or
``invalid``) and ``registrations`` (startup sync ``synced``, ``skipped``
or ``failed``). ``auth`` reports the configured token validators
(``oidc``, ``dev``, ``oidc+dev`` or ``unconfigured``; with
``unconfigured`` every protected route answers 503) and ``rbac``
whether any role grants a permission (``configured`` or ``empty``).
``version`` is the running application version (``ADRIANO_VERSION``).
Configuration problems never make the probe fail: restarting the
container would not fix them. The route is public and reports no
secrets and no record data.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth.status import auth_status
from app.composition import CatalogRuntime, get_catalog_runtime
from app.config import Settings, get_settings
from app.database import get_db

router = APIRouter()

_UNKNOWN = "unknown"


def _config_status(runtime: CatalogRuntime | None) -> dict[str, str]:
    """
    Summarise the startup configuration state.

    :param runtime: Startup state, ``None`` if the lifespan did not run.
    :returns: ``config``, ``policy``, ``registrations`` and ``rbac``
        keys.
    """
    if runtime is None:
        return {
            "config": _UNKNOWN,
            "policy": _UNKNOWN,
            "registrations": _UNKNOWN,
            "rbac": _UNKNOWN,
        }
    return {
        "config": runtime.config.file_status.value,
        "policy": runtime.config.policy.status.value,
        "registrations": runtime.sync.value,
        "rbac": "configured" if runtime.config.rbac.roles else "empty",
    }


@router.get("/healthz")
def healthz(
    response: Response,
    db: Session = Depends(get_db),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Report application, database and configuration health.

    Returns HTTP 200 with ``status: ok`` when the database is
    reachable, or HTTP 503 with ``status: degraded`` otherwise. The
    ``config``, ``policy`` and ``registrations`` keys report the
    configuration loaded at startup.

    :param response: Outgoing response, used to set the status code.
    :param db: Request-scoped database session.
    :param runtime: Startup state of the catalog.
    :param settings: Application settings (auth status).
    :returns: A mapping with ``status``, ``database``, ``config``,
        ``policy``, ``registrations``, ``rbac``, ``auth`` and
        ``version`` keys.
    """
    details = _config_status(runtime)
    details["auth"] = auth_status(settings).value
    details["version"] = settings.version
    try:
        db.execute(text("SELECT 1"))
    except OperationalError:
        response.status_code = 503
        return {"status": "degraded", "database": "unavailable", **details}
    return {"status": "ok", "database": "ok", **details}
