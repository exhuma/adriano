"""
Not-indexed list queries of the PostgreSQL store.

Entries are keyed by location (``pk_not_indexed``: source, project,
path, ref). An upsert keeps ``first_seen_at`` and moves
``last_seen_at``. Deciding when an entry is written or cleared is up
to intake (:mod:`app.services.poll_apply`).

Public API: :func:`put_not_indexed`, :func:`list_not_indexed`,
:func:`delete_not_indexed`.
"""

from collections.abc import Collection

from sqlalchemy import Table, delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.storage.port import (
    IntakeKind,
    NotIndexedEntry,
    NotIndexedKey,
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
