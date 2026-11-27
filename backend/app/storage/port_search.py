"""
Catalog search and its facets.

Part of the :class:`app.storage.port.CatalogStore` protocol, split by
concern to keep modules small. Import :class:`SearchStore` only to compose
the store; services depend on :mod:`app.storage.port`.

Public API: :class:`SearchStore`.
"""

from typing import Protocol

from app.domain.approval import Policy
from app.storage.search_values import FacetEntry, SearchFilters, SearchPage
from app.storage.values import SearchSort


class SearchStore(Protocol):
    """Catalog search and its facets."""

    def list_facets(self) -> list[FacetEntry]:
        """
        Count decision ADRs per ``(source_id, project)``, for filter UIs.

        Counts distinct UUIDs (an ADR with candidates counts once), from
        published and candidate rows, but not errata (matching the
        default ``record_type=decision`` search).

        :returns: One entry per non-empty ``(source_id, project)``
            pair, ordered by source id then project.
        """
        ...

    def search(
        self,
        query: str | None,
        filters: SearchFilters,
        page: int,
        page_size: int,
        *,
        policy: Policy | None,
        sort: SearchSort = SearchSort.RELEVANCE,
    ) -> SearchPage:
        """
        Full-text search with filters and bounded pagination.

        Hits are ordered by *sort* (see :class:`SearchSort`); the
        default ranks by relevance when *query* is given, else orders
        by title.

        :param query: Free text (titles, bodies, UUIDs, paths); blank or
            ``None`` matches everything.
        :param filters: Filters.
        :param page: 1-based page number.
        :param page_size: Page size, 1 to :data:`MAX_PAGE_SIZE`.
        :param policy: The configured policy (``None`` when missing or
            invalid), used for approval states.
        :param sort: Result order; ``relevance`` without a query
            falls back to ``title``.
        :returns: The page.
        :raises ValueError: If *page* or *page_size* is out of bounds.
        """
        ...
