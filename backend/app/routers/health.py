"""Health-check route used by deployment and container probes.

``GET /healthz`` reports whether the application can reach its
database. It intentionally performs no business logic and depends
only on the shared ``get_db`` session dependency, so it reflects the
same connectivity every other route relies on.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/healthz")
def healthz(
    response: Response, db: Session = Depends(get_db)
) -> dict[str, str]:
    """Report application and database health.

    Returns HTTP 200 with ``status: ok`` when the database is
    reachable, or HTTP 503 with ``status: degraded`` otherwise.

    :param response: Outgoing response, used to set the status code.
    :param db: Request-scoped database session.
    :returns: A mapping with ``status`` and ``database`` keys.
    """
    try:
        db.execute(text("SELECT 1"))
    except OperationalError:
        response.status_code = 503
        return {"status": "degraded", "database": "unavailable"}
    return {"status": "ok", "database": "ok"}
