"""
The not-indexed queue of documents intake could not index.

Part of the :class:`app.storage.port.CatalogStore` protocol, split by
concern to keep modules small. Import :class:`NotIndexedStore` only to compose
the store; services depend on :mod:`app.storage.port`.

Public API: :class:`NotIndexedStore`.
"""

from collections.abc import Collection
from typing import Protocol

from app.storage.queue_values import (
    NotIndexedEntry,
    NotIndexedFilters,
    NotIndexedKey,
    NotIndexedPage,
    NotIndexedWrite,
)
from app.storage.values import IntakeKind, Location


class NotIndexedStore(Protocol):
    """The not-indexed queue of documents intake could not index."""

    def put_not_indexed(self, entry: NotIndexedWrite) -> None:
        """
        Insert or replace a not-indexed entry at its key.

        ``first_seen_at`` is kept for an existing key; ``last_seen_at``
        moves to now.

        :param entry: The entry.
        """
        ...

    def list_not_indexed(
        self, source_id: str | None = None, origin: IntakeKind | None = None
    ) -> list[NotIndexedEntry]:
        """
        List not-indexed entries.

        :param source_id: Restrict to one registration; ``None`` = all.
        :param origin: Restrict to one intake; ``None`` = both.
        :returns: Entries ordered by key.
        """
        ...

    def page_not_indexed(
        self, filters: NotIndexedFilters, page: int, page_size: int
    ) -> NotIndexedPage:
        """
        List one page of not-indexed entries, newest first.

        :param filters: Filters.
        :param page: 1-based page number.
        :param page_size: Page size, 1 to :data:`MAX_PAGE_SIZE`.
        :returns: The page, ordered by ``last_seen_at`` descending, then
            by key.
        :raises ValueError: If *page* or *page_size* is out of bounds.
        """
        ...

    def get_not_indexed(self, key: NotIndexedKey) -> NotIndexedEntry | None:
        """
        Fetch one not-indexed entry.

        :param key: Its location.
        :returns: The entry, or ``None``.
        """
        ...

    def count_not_indexed(self) -> dict[str, int]:
        """
        Count not-indexed entries per registration.

        :returns: Count by registration id; registrations without
            entries are absent.
        """
        ...

    def clear_pushed_at(self, locations: Collection[Location]) -> int:
        """
        Delete every push entry at the given file locations.

        A poll that indexes a document at a file location settles
        whatever a push was refused there, whatever its ref or reason:
        an author who fixed the document and merged it no longer has a
        problem to resolve.

        :param locations: File locations a poll just indexed.
        :returns: Number of deleted entries; no query for no locations.
        """
        ...

    def delete_not_indexed(self, keys: Collection[NotIndexedKey]) -> int:
        """
        Delete not-indexed entries (automatic clearing only).

        :param keys: Keys to delete; unknown keys are ignored.
        :returns: Number of deleted entries.
        """
        ...
