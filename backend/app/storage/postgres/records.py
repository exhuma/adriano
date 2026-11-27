"""
Record and revision queries of the PostgreSQL store.

A record row is keyed by its ADR UUID: the published row by
``adr_uuid`` alone (partial unique index ``uq_record_published_uuid``),
a candidate by ``(adr_uuid, ref)`` (the primary key
``(adr_uuid, kind, ref)``). Upserts use ``INSERT ... ON CONFLICT``
against those. The search vector is maintained by a database trigger,
so it is never written here.

Public API: :func:`put_revision`, :func:`get_revision`,
:func:`upsert_record`, :func:`create_candidate`, :func:`get_record`,
:func:`list_records`, :func:`list_change_tokens`,
:func:`list_published_entries`, :func:`set_change_token`,
:func:`delete_published`, :func:`list_relationship_candidates`,
:func:`list_facets`.
"""

import uuid
from collections.abc import Collection
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Table,
    TextClause,
    and_,
    case,
    delete,
    func,
    literal_column,
    or_,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.orm import Session

from app.domain.relationships import RecordSummary
from app.domain.values import Links, RecordKind
from app.errors import CandidateExistsError
from app.storage.port import (
    ChangeTokenEntry,
    FacetEntry,
    RecordState,
    RecordWrite,
    Revision,
    StoredRecord,
    UpsertResult,
)
from app.storage.postgres import convert
from app.storage.postgres.models import RecordRow, RevisionRow

RECORD: Table = RecordRow.__table__  # type: ignore[assignment]
REVISION: Table = RevisionRow.__table__  # type: ignore[assignment]

#: Conflict target columns and index predicate per state. The predicate
#: of the published key must be a SQL literal identical to the partial
#: index definition so PostgreSQL can infer the index.
_CONFLICT_KEYS: dict[RecordState, tuple[tuple[str, ...], TextClause | None]] = {
    RecordState.PUBLISHED: (("adr_uuid",), text("kind = 'published'")),
    RecordState.CANDIDATE: (("adr_uuid", "kind", "ref"), None),
}

_LOCATION = ("source_id", "project", "path")

_PUBLISHED = RECORD.c.kind == RecordState.PUBLISHED.value


def put_revision(session: Session, digest: str, content: str) -> bool:
    """
    Store a snapshot unless it exists.

    :param session: Unit-of-work session.
    :param digest: Digest string.
    :param content: Canonical text.
    :returns: ``True`` if newly stored.
    """
    stmt = (
        insert(REVISION)
        .values(digest=digest, content=content)
        .on_conflict_do_nothing(index_elements=["digest"])
        .returning(REVISION.c.digest)
    )
    return session.execute(stmt).first() is not None


def get_revision(session: Session, digest: str) -> Revision | None:
    """
    Fetch a snapshot.

    :param session: Unit-of-work session.
    :param digest: Digest string.
    :returns: The snapshot, or ``None``.
    """
    row = (
        session.execute(select(REVISION).where(REVISION.c.digest == digest))
        .mappings()
        .first()
    )
    return None if row is None else convert.revision(row)


def _key_condition(
    adr_uuid: uuid.UUID, kind: RecordState, ref: str | None
) -> ColumnElement[bool]:
    """
    Build the WHERE clause that finds one row by its key.

    :param adr_uuid: The ADR's UUID.
    :param kind: Published or candidate.
    :param ref: The candidate's ref (ignored for the published row).
    :returns: The condition.
    """
    conditions = [
        RECORD.c.adr_uuid == adr_uuid,
        RECORD.c.kind == kind.value,
    ]
    if kind is RecordState.CANDIDATE:
        conditions.append(RECORD.c.ref == ref)
    return and_(*conditions)


def _upsert_set(stmt: Insert, values: dict[str, Any]) -> dict[str, Any]:
    """
    Build the ``ON CONFLICT DO UPDATE SET`` clause.

    ``previous_digest`` and ``updated_at`` only move when the digest
    changes; ``first_seen_at`` is kept.

    :param stmt: The insert statement.
    :param values: Inserted column values.
    :returns: Column name -> expression.
    """
    excluded = stmt.excluded
    changed = RECORD.c.digest.is_distinct_from(excluded.digest)
    result: dict[str, Any] = {name: excluded[name] for name in values}
    result["previous_digest"] = case(
        (changed, RECORD.c.digest), else_=RECORD.c.previous_digest
    )
    result["updated_at"] = case(
        (changed, func.now()), else_=RECORD.c.updated_at
    )
    result["last_seen_at"] = func.now()
    return result


def upsert_record(
    session: Session, record: RecordWrite, kind: RecordState
) -> UpsertResult:
    """
    Insert or replace a published or candidate row.

    :param session: Unit-of-work session.
    :param record: Row content.
    :param kind: Published or candidate.
    :returns: The outcome.
    """
    old = (
        session.execute(
            select(RECORD.c.digest, *(RECORD.c[name] for name in _LOCATION))
            .where(_key_condition(record.adr_uuid, kind, record.ref))
            .with_for_update()
        )
        .mappings()
        .first()
    )
    columns, predicate = _CONFLICT_KEYS[kind]
    values = convert.record_values(record, kind)
    stmt = insert(RECORD).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=list(columns),
        index_where=predicate,
        set_=_upsert_set(stmt, values),
    ).returning(
        RECORD.c.previous_digest,
        literal_column("(xmax = 0)").label("created"),
    )
    row = session.execute(stmt).one()
    created = bool(row.created)
    moved = old is not None and any(
        old[name] != values[name] for name in _LOCATION
    )
    return UpsertResult(
        created=created,
        digest_changed=old is not None and old["digest"] != record.digest,
        previous_digest=row.previous_digest,
        moved=moved,
    )


def create_candidate(session: Session, record: RecordWrite) -> UpsertResult:
    """
    Insert a candidate row only if its key is free.

    :param session: Unit-of-work session.
    :param record: Row content.
    :returns: The outcome.
    :raises CandidateExistsError: If the candidate exists.
    """
    columns, _predicate = _CONFLICT_KEYS[RecordState.CANDIDATE]
    stmt = (
        insert(RECORD)
        .values(convert.record_values(record, RecordState.CANDIDATE))
        .on_conflict_do_nothing(index_elements=list(columns))
        .returning(RECORD.c.adr_uuid)
    )
    if session.execute(stmt).scalar_one_or_none() is None:
        raise CandidateExistsError(
            f"candidate {record.adr_uuid} on ref {record.ref!r} exists"
        )
    return UpsertResult(
        created=True, digest_changed=False, previous_digest=None
    )


def get_record(
    session: Session, adr_uuid: uuid.UUID, kind: RecordState, ref: str | None
) -> StoredRecord | None:
    """
    Fetch one record row by its key.

    :param session: Unit-of-work session.
    :param adr_uuid: The ADR's UUID.
    :param kind: Published or candidate.
    :param ref: The candidate's ref (ignored for the published row).
    :returns: The row, or ``None``.
    """
    row = (
        session.execute(
            select(RECORD).where(_key_condition(adr_uuid, kind, ref))
        )
        .mappings()
        .first()
    )
    return None if row is None else convert.stored_record(row)


def list_records(session: Session, adr_uuid: uuid.UUID) -> list[StoredRecord]:
    """
    List every row of an ADR.

    :param session: Unit-of-work session.
    :param adr_uuid: The ADR's UUID.
    :returns: The published row first, then candidates by ref.
    """
    stmt = (
        select(RECORD)
        .where(RECORD.c.adr_uuid == adr_uuid)
        .order_by(~_PUBLISHED, RECORD.c.ref)
    )
    rows = session.execute(stmt).mappings()
    return [convert.stored_record(row) for row in rows]


_ENTRY_COLUMNS = (
    RECORD.c.adr_uuid,
    RECORD.c.source_id,
    RECORD.c.project,
    RECORD.c.path,
    RECORD.c.change_token,
    RECORD.c.digest,
)


def list_change_tokens(
    session: Session, source_id: str, project: str | None
) -> list[ChangeTokenEntry]:
    """
    List the published files of a registration with their tokens.

    :param session: Unit-of-work session.
    :param source_id: Registration id.
    :param project: Restrict to one project, or ``None``.
    :returns: Entries ordered by project and path.
    """
    stmt = select(*_ENTRY_COLUMNS).where(
        _PUBLISHED, RECORD.c.source_id == source_id
    )
    if project is not None:
        stmt = stmt.where(RECORD.c.project == project)
    rows = session.execute(stmt.order_by(RECORD.c.project, RECORD.c.path))
    return [ChangeTokenEntry(**row) for row in rows.mappings()]


def list_published_entries(
    session: Session, uuids: Collection[uuid.UUID]
) -> list[ChangeTokenEntry]:
    """
    List where the published rows of some UUIDs live.

    :param session: Unit-of-work session.
    :param uuids: ADR UUIDs; empty means no query.
    :returns: One entry per UUID with a published row.
    """
    if not uuids:
        return []
    stmt = select(*_ENTRY_COLUMNS).where(
        _PUBLISHED, RECORD.c.adr_uuid.in_(list(uuids))
    )
    return [ChangeTokenEntry(**row) for row in session.execute(stmt).mappings()]


def _at_location(entry: ChangeTokenEntry) -> ColumnElement[bool]:
    """
    Match the published row of an entry at the entry's location.

    :param entry: UUID and expected location.
    :returns: The condition.
    """
    return and_(
        _PUBLISHED,
        RECORD.c.adr_uuid == entry.adr_uuid,
        RECORD.c.source_id == entry.source_id,
        RECORD.c.project == entry.project,
        RECORD.c.path == entry.path,
    )


def set_change_token(
    session: Session, entry: ChangeTokenEntry, change_token: str | None
) -> bool:
    """
    Rewrite the change token of a published row still at its location.

    ``last_seen_at`` moves too, like any ingest write.

    :param session: Unit-of-work session.
    :param entry: UUID and expected location.
    :param change_token: The new token.
    :returns: ``True`` if a row was updated.
    """
    stmt = (
        update(RECORD)
        .where(_at_location(entry))
        .values(change_token=change_token, last_seen_at=func.now())
        .returning(RECORD.c.adr_uuid)
    )
    return session.execute(stmt).first() is not None


def delete_published(
    session: Session, entries: Collection[ChangeTokenEntry]
) -> int:
    """
    Delete published rows still at their expected locations.

    Candidates are never deleted here.

    :param session: Unit-of-work session.
    :param entries: UUIDs with their expected locations.
    :returns: Number of deleted rows.
    """
    if not entries:
        return 0
    keys = [(e.adr_uuid, e.source_id, e.project, e.path) for e in entries]
    stmt = (
        delete(RECORD)
        .where(
            _PUBLISHED,
            tuple_(
                RECORD.c.adr_uuid,
                RECORD.c.source_id,
                RECORD.c.project,
                RECORD.c.path,
            ).in_(keys),
        )
        .returning(RECORD.c.adr_uuid)
    )
    return len(session.execute(stmt).all())


def list_relationship_candidates(
    session: Session,
    self_uuid: uuid.UUID,
    link_targets: Collection[uuid.UUID],
) -> list[RecordSummary]:
    """
    List the published rows that can affect one record's relationships.

    Instead of every published row, this returns only the rows that
    :class:`~app.domain.relationships.RelationshipIndex` could use for
    *self_uuid*'s view:

    - rows whose UUID is one of *link_targets* (the record's own
      outbound links);
    - rows that link to *self_uuid* via ``updates``, ``obsoletes`` or
      ``corrects`` (inbound links and errata).

    The record's own published row is not returned: the caller adds the
    row being viewed (see :mod:`app.services.record_relationships`).
    The planner still scans every published row (``links`` has no
    index), but only matching rows are sent to the client (see
    ``docs/developer/performance.rst``).

    :param session: Unit-of-work session.
    :param self_uuid: The viewed record's own UUID.
    :param link_targets: UUIDs the viewed record's own ``updates``,
        ``obsoletes`` and ``corrects`` links target.
    :returns: One summary per matching published ADR, ordered by UUID.
    """
    target = str(self_uuid)
    stmt = (
        select(RECORD.c.adr_uuid, RECORD.c.links, RECORD.c.record_kind)
        .where(
            _PUBLISHED,
            RECORD.c.adr_uuid != self_uuid,
            or_(
                RECORD.c.adr_uuid.in_(list(link_targets)),
                RECORD.c.links["updates"].op("?")(target),
                RECORD.c.links["obsoletes"].op("?")(target),
                RECORD.c.links["corrects"].astext == target,
            ),
        )
        .order_by(RECORD.c.adr_uuid)
    )
    return [
        RecordSummary(
            adr_uuid=row["adr_uuid"],
            links=Links.from_dict(row["links"]),
            record_kind=RecordKind(row["record_kind"]),
        )
        for row in session.execute(stmt).mappings()
    ]


def list_facets(session: Session) -> list[FacetEntry]:
    """
    Count decision UUIDs per ``(source_id, project)``, for filter UIs.

    Errata are not counted, matching the default search.

    :param session: Unit-of-work session.
    :returns: One entry per pair, ordered by source id then project.
    """
    stmt = (
        select(
            RECORD.c.source_id,
            RECORD.c.project,
            func.count(RECORD.c.adr_uuid.distinct()).label("count"),
        )
        .where(RECORD.c.record_kind == RecordKind.DECISION.value)
        .group_by(RECORD.c.source_id, RECORD.c.project)
        .order_by(RECORD.c.source_id, RECORD.c.project)
    )
    return [
        FacetEntry(
            source_id=row["source_id"],
            project=row["project"],
            count=row["count"],
        )
        for row in session.execute(stmt).mappings()
    ]
