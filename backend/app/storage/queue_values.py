"""
Value types of the not-indexed list, crossing the storage port.

The not-indexed list (a dead-letter queue) holds every document intake
found but could not index: no valid UUID, unparseable frontmatter, a
losing duplicate UUID, or content that could not be read. Such a
document has no identity, so an entry is keyed by where it was found:
``(source_id, project, path, ref)``. Entries are never dismissed by
hand; intake clears them (see :mod:`app.services.poll_apply`).

Plain frozen dataclasses, independent of any ORM; kept apart from
:mod:`app.storage.values` only to keep modules small. Import them
through :mod:`app.storage.port`, which re-exports them.

Public API: :class:`NotIndexedKey`, :class:`NotIndexedWrite`,
:class:`NotIndexedEntry`, :class:`NotIndexedFilters`,
:class:`NotIndexedPage`.
"""

import datetime
import uuid
from dataclasses import dataclass

from app.domain.issues import Issue, IssueCode
from app.storage.values import IntakeKind, Location


@dataclass(frozen=True, slots=True, order=True)
class NotIndexedKey:
    """
    Where a not-indexed document was found.

    :param source_id: Registration id.
    :param project: Project path.
    :param path: File path inside the project.
    :param ref: Branch/ref the document was read from.
    """

    source_id: str
    project: str
    path: str
    ref: str

    @property
    def location(self) -> Location:
        """
        The file location, without the ref.

        :returns: ``(source_id, project, path)``.
        """
        return Location(self.source_id, self.project, self.path)


@dataclass(frozen=True, slots=True, kw_only=True)
class NotIndexedWrite:
    """
    Everything intake writes for one not-indexed document.

    The revision for :attr:`digest`, if any, must have been stored
    first (:meth:`app.storage.port.CatalogStore.put_revision`).

    :param key: Where the document was found.
    :param origin: The intake that found it (poll or push).
    :param reasons: Why it is not indexed (error issues).
    :param digest: Digest of the content as found; ``None`` when it
        could not be read.
    :param holder_uuid: For a losing duplicate, the UUID it claims
        (held by another file).
    :param change_token: Source change token; ``None`` makes the next
        poll read the file again.
    :param source_url: Link to the file at the source, if any.
    """

    key: NotIndexedKey
    origin: IntakeKind
    reasons: tuple[Issue, ...]
    digest: str | None = None
    holder_uuid: uuid.UUID | None = None
    change_token: str | None = None
    source_url: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class NotIndexedEntry(NotIndexedWrite):
    """
    A stored not-indexed entry.

    :param first_seen_at: When intake first listed the location.
    :param last_seen_at: When intake last wrote the entry.
    """

    first_seen_at: datetime.datetime
    last_seen_at: datetime.datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class NotIndexedFilters:
    """
    Filters of the not-indexed list; ``None`` means no restriction.

    :param source_id: Registration id.
    :param project: Project path.
    :param reason: Entries carrying this reason code.
    :param origin: Entries found by this intake.
    """

    source_id: str | None = None
    project: str | None = None
    reason: IssueCode | None = None
    origin: IntakeKind | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class NotIndexedPage:
    """
    One page of the not-indexed list.

    :param items: Entries on this page, newest ``last_seen_at`` first.
    :param total: Number of entries over all pages.
    :param page: 1-based page number.
    :param page_size: Requested page size.
    """

    items: tuple[NotIndexedEntry, ...]
    total: int
    page: int
    page_size: int
