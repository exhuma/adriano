"""
Not-indexed list queries of the PostgreSQL store.

Entries are keyed by location (``pk_not_indexed``: source, project,
path, ref). An upsert keeps ``first_seen_at`` and moves
``last_seen_at``. Deciding when an entry is written or cleared is up
to intake (:mod:`app.services.poll_apply`).

Public API: :func:`put_not_indexed`, :func:`list_not_indexed`,
:func:`clear_pushed_at`,
:func:`page_not_indexed`, :func:`get_not_indexed`,
:func:`count_not_indexed`, :func:`delete_not_indexed`.
"""

from collections.abc import Collection

from sqlalchemy import ColumnElement, Table, delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.storage.port import (
    MAX_PAGE_SIZE,
    IntakeKind,
    Location,
    NotIndexedEntry,
    NotIndexedFilters,
    NotIndexedKey,
    NotIndexedPage,
    NotIndexedWrite,
)
from app.storage.postgres import convert
from app.storage.postgres.models import NotIndexedRow

QUEUE: Table = NotIndexedRow.__table__  # type: ignore[assignment]

_KEY = ("source_id", "project", "path", "ref")


def put_not_indexed(session: Session, entry: NotIndexedWrite) -> None:
    """
    Insert or replace an entry at its key.

    :param session: Unit-of-work session.
    :param entry: The entry.
    """
    values = convert.not_indexed_values(entry)
    stmt = insert(QUEUE).values(values)
    update = {name: stmt.excluded[name] for name in values if name not in _KEY}
    update["last_seen_at"] = func.now()
    session.execute(
        stmt.on_conflict_do_update(index_elements=list(_KEY), set_=update)
    )


def list_not_indexed(
    session: Session, source_id: str | None, origin: IntakeKind | None
) -> list[NotIndexedEntry]:
    """
    List entries, optionally of one registration and origin.

    :param session: Unit-of-work session.
    :param source_id: Registration id, or ``None`` for all.
    :param origin: Poll or push, or ``None`` for both.
    :returns: Entries ordered by key.
    """
    stmt = select(QUEUE)
    if source_id is not None:
        stmt = stmt.where(QUEUE.c.source_id == source_id)
    if origin is not None:
        stmt = stmt.where(QUEUE.c.origin == origin.value)
    stmt = stmt.order_by(*(QUEUE.c[name] for name in _KEY))
    return [
        convert.not_indexed(row) for row in session.execute(stmt).mappings()
    ]


def _where(filters: NotIndexedFilters) -> list[ColumnElement[bool]]:
    """
    Translate list filters into WHERE conditions.

    :param filters: The filters.
    :returns: Conditions to AND together.
    """
    result: list[ColumnElement[bool]] = []
    if filters.source_id is not None:
        result.append(QUEUE.c.source_id == filters.source_id)
    if filters.project is not None:
        result.append(QUEUE.c.project == filters.project)
    if filters.origin is not None:
        result.append(QUEUE.c.origin == filters.origin.value)
    if filters.reason is not None:
        result.append(
            QUEUE.c.reasons.contains([{"code": filters.reason.value}])
        )
    return result


def page_not_indexed(
    session: Session, filters: NotIndexedFilters, page: int, page_size: int
) -> NotIndexedPage:
    """
    List one filtered page, newest ``last_seen_at`` first.

    :param session: Unit-of-work session.
    :param filters: Filters.
    :param page: 1-based page number.
    :param page_size: Page size, 1 to :data:`MAX_PAGE_SIZE`.
    :returns: The page.
    :raises ValueError: If *page* or *page_size* is out of bounds.
    """
    if page < 1:
        raise ValueError(f"page must be >= 1, got {page}")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(
            f"page_size must be between 1 and {MAX_PAGE_SIZE}, got {page_size}"
        )
    where = _where(filters)
    total = session.execute(
        select(func.count()).select_from(QUEUE).where(*where)
    ).scalar_one()
    stmt = (
        select(QUEUE)
        .where(*where)
        .order_by(QUEUE.c.last_seen_at.desc(), *(QUEUE.c[n] for n in _KEY))
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return NotIndexedPage(
        items=tuple(
            convert.not_indexed(row) for row in session.execute(stmt).mappings()
        ),
        total=total,
        page=page,
        page_size=page_size,
    )


def get_not_indexed(
    session: Session, key: NotIndexedKey
) -> NotIndexedEntry | None:
    """
    Fetch one entry by key.

    :param session: Unit-of-work session.
    :param key: The location.
    :returns: The entry, or ``None``.
    """
    stmt = select(QUEUE).where(
        QUEUE.c.source_id == key.source_id,
        QUEUE.c.project == key.project,
        QUEUE.c.path == key.path,
        QUEUE.c.ref == key.ref,
    )
    row = session.execute(stmt).mappings().first()
    return None if row is None else convert.not_indexed(row)


def count_not_indexed(session: Session) -> dict[str, int]:
    """
    Count entries per registration.

    :param session: Unit-of-work session.
    :returns: Count by registration id.
    """
    stmt = select(QUEUE.c.source_id, func.count()).group_by(QUEUE.c.source_id)
    return {source_id: count for source_id, count in session.execute(stmt)}


def clear_pushed_at(session: Session, locations: Collection[Location]) -> int:
    """
    Delete every push entry at the given file locations, any ref.

    :param session: Unit-of-work session.
    :param locations: File locations a poll just indexed.
    :returns: Number of deleted entries; no query for no locations.
    """
    if not locations:
        return 0
    values = {(loc.source_id, loc.project, loc.path) for loc in locations}
    columns = (QUEUE.c.source_id, QUEUE.c.project, QUEUE.c.path)
    stmt = (
        delete(QUEUE)
        .where(
            QUEUE.c.origin == IntakeKind.PUSH.value,
            tuple_(*columns).in_(values),
        )
        .returning(QUEUE.c.path)
    )
    return len(session.execute(stmt).all())


def delete_not_indexed(
    session: Session, keys: Collection[NotIndexedKey]
) -> int:
    """
    Delete entries by key.

    :param session: Unit-of-work session.
    :param keys: Keys to delete; empty means no query.
    :returns: Number of deleted entries.
    """
    if not keys:
        return 0
    values = [(k.source_id, k.project, k.path, k.ref) for k in keys]
    stmt = (
        delete(QUEUE)
        .where(tuple_(*(QUEUE.c[name] for name in _KEY)).in_(values))
        .returning(QUEUE.c.path)
    )
    return len(session.execute(stmt).all())
