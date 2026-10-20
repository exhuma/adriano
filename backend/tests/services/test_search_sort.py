"""Unit tests for the search sort defaults (:func:`resolve_sort`)."""

import pytest

from app.services.search import resolve_sort
from app.storage.port import SearchSort


@pytest.mark.parametrize(
    ("sort", "query", "expected"),
    [
        (None, None, SearchSort.TITLE),
        (None, "   ", SearchSort.TITLE),
        (None, "postgres", SearchSort.RELEVANCE),
        (SearchSort.RELEVANCE, None, SearchSort.TITLE),
        (SearchSort.RELEVANCE, "", SearchSort.TITLE),
        (SearchSort.RELEVANCE, "postgres", SearchSort.RELEVANCE),
        (SearchSort.TITLE, "postgres", SearchSort.TITLE),
        (SearchSort.RECENT, None, SearchSort.RECENT),
        (SearchSort.RECENT, "postgres", SearchSort.RECENT),
    ],
)
def test_resolve_sort(
    sort: SearchSort | None, query: str | None, expected: SearchSort
) -> None:
    """Ensure the default and the no-query fallback of the sort."""
    assert resolve_sort(sort, query) is expected
