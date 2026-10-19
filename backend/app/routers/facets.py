"""
HTTP route for search filter options.

``GET /api/v1/facets`` lists sources and their projects with record
counts, for the search landing page's source/project selects.
"""

from fastapi import APIRouter, Depends

from app.auth.deps import require_permission
from app.auth.rbac import Permission
from app.composition import get_store_provider
from app.schemas.sources import FacetsOut
from app.services import catalog
from app.storage.port import CatalogStoreProvider

router = APIRouter(
    prefix="/api/v1",
    tags=["facets"],
    dependencies=[Depends(require_permission(Permission.READ))],
)


@router.get("/facets", response_model=FacetsOut)
def get_facets(
    provider: CatalogStoreProvider = Depends(get_store_provider),
) -> FacetsOut:
    """
    List sources and their projects with record counts.

    :param provider: Storage provider (overridden by tests).
    :returns: The facets.
    """
    with provider.unit_of_work() as store:
        facets = catalog.get_facets(store)
    return FacetsOut.model_validate(facets)
