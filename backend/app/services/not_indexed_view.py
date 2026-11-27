"""
Read-only views of the not-indexed list.

The list holds every document intake could not index (see
:mod:`app.storage.queue_values`). Same rules as
:mod:`app.services.search`: a :class:`~app.storage.port.CatalogStore`
inside the caller's unit of work in, plain dataclasses out.

Public API: :class:`NotIndexedItem`, :class:`NotIndexedDetail`,
:class:`NotIndexedListPage`, :func:`list_not_indexed`,
:func:`get_not_indexed_detail`.
"""

import datetime
import uuid
from dataclasses import dataclass

from app.domain.issues import Issue
from app.storage.port import (
    CatalogStore,
    IntakeKind,
    NotIndexedEntry,
    NotIndexedFilters,
    NotIndexedKey,
)

__all__ = [
    "NotIndexedDetail",
    "NotIndexedItem",
    "NotIndexedListPage",
    "get_not_indexed_detail",
    "list_not_indexed",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class NotIndexedItem:
    """
    One document intake could not index.

    :param source_id: Registration id of the location.
    :param project: Project path of the location.
    :param path: File path of the location.
    :param ref: Branch/ref the document was read from or pushed to.
    :param origin: The intake that found it (poll or push).
    :param reasons: Why it is not indexed.
    :param holder_uuid: For a duplicate UUID, the UUID (it addresses
        the ADR that holds it).
    :param source_url: Link to the file at the source, if any.
    :param first_seen_at: When intake first saw the location.
    :param last_seen_at: When intake last wrote the entry.
    :param has_content: Whether the rejected content is stored.
    """

    source_id: str
    project: str
    path: str
    ref: str
    origin: IntakeKind
    reasons: tuple[Issue, ...]
    holder_uuid: uuid.UUID | None
    source_url: str | None
    first_seen_at: datetime.datetime
    last_seen_at: datetime.datetime
    has_content: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class NotIndexedDetail(NotIndexedItem):
    """
    A not-indexed entry with its rejected content.

    :param content: The content as intake found it (canonical text);
        ``None`` when it could not be read.
    """

    content: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class NotIndexedListPage:
    """
    One page of the not-indexed list.

    :param items: Entries, newest ``last_seen_at`` first.
    :param total: Number of entries over all pages.
    :param page: 1-based page number.
    :param page_size: Requested page size.
    """

    items: tuple[NotIndexedItem, ...]
    total: int
    page: int
    page_size: int


def _item(entry: NotIndexedEntry) -> NotIndexedItem:
    """Convert a stored entry to the list item."""
    return NotIndexedItem(
        source_id=entry.key.source_id,
        project=entry.key.project,
        path=entry.key.path,
        ref=entry.key.ref,
        origin=entry.origin,
        reasons=entry.reasons,
        holder_uuid=entry.holder_uuid,
        source_url=entry.source_url,
        first_seen_at=entry.first_seen_at,
        last_seen_at=entry.last_seen_at,
        has_content=entry.digest is not None,
    )


def list_not_indexed(
    store: CatalogStore,
    filters: NotIndexedFilters,
    page: int,
    page_size: int,
) -> NotIndexedListPage:
    """
    List one page of the not-indexed list.

    :param store: Store of the caller's unit of work.
    :param filters: Filters.
    :param page: 1-based page number.
    :param page_size: Page size, 1 to
        :data:`~app.storage.port.MAX_PAGE_SIZE`.
    :returns: The page.
    """
    result = store.page_not_indexed(filters, page, page_size)
    return NotIndexedListPage(
        items=tuple(_item(entry) for entry in result.items),
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


def get_not_indexed_detail(
    store: CatalogStore, key: NotIndexedKey
) -> NotIndexedDetail | None:
    """
    Fetch one entry with its rejected content.

    :param store: Store of the caller's unit of work.
    :param key: The location.
    :returns: The detail, or ``None`` if there is no such entry.
    """
    entry = store.get_not_indexed(key)
    if entry is None:
        return None
    revision = (
        store.get_revision(entry.digest) if entry.digest is not None else None
    )
    item = _item(entry)
    return NotIndexedDetail(
        **{name: getattr(item, name) for name in item.__slots__},
        content=None if revision is None else revision.content,
    )
