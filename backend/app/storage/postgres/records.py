"""
Record and revision queries of the PostgreSQL store.

Upserts use ``INSERT ... ON CONFLICT`` against the partial unique
indexes ``uq_record_published_location`` and
``uq_record_candidate_identity_ref``. The search vector is maintained by
a database trigger, so it is never written here.

Public API: :func:`put_revision`, :func:`get_revision`,
:func:`upsert_record`, :func:`create_candidate`, :func:`get_record`,
:func:`list_change_tokens`, :func:`delete_published`,
:func:`list_identity_siblings`, :func:`list_relationship_summaries`,
:func:`list_relationship_candidates`, :func:`list_facets`.
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
)
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.orm import Session

from app.domain.relationships import RecordSummary
from app.domain.values import Identity, Links, RecordKind
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

#: Conflict target columns and partial-index predicate per state. The
#: predicate must be a SQL literal identical to the index definition so
#: PostgreSQL can infer the partial unique index.
_CONFLICT_KEYS: dict[RecordState, tuple[tuple[str, ...], TextClause]] = {
    RecordState.PUBLISHED: (
        ("source_id", "project", "path"),
        text("kind = 'published'"),
    ),
    RecordState.CANDIDATE: (
        ("source_id", "project", "record_key", "ref"),
        text("kind = 'candidate'"),
    ),
}


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
    record: RecordWrite, kind: RecordState
) -> ColumnElement[bool]:
    """
    Build the WHERE clause that finds the row an upsert would hit.

    :param record: Row content.
    :param kind: Published or candidate.
    :returns: The condition.
    """
    columns, predicate = _CONFLICT_KEYS[kind]
    values = convert.record_values(record, kind)
    return and_(
        predicate, *(RECORD.c[name] == values[name] for name in columns)
    )


def _upsert_set(stmt: Insert, values: dict[str, Any]) -> dict[str, Any]:
    """
    Build the ``ON CONFLICT DO UPDATE SET`` clause.

    ``previous_digest`` and ``updated_at`` only move when the digest
    changes; ``first_seen_at`` and ``id`` are kept.

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
    old_digest = session.execute(
        select(RECORD.c.digest)
        .where(_key_condition(record, kind))
        .with_for_update()
    ).scalar_one_or_none()
    columns, predicate = _CONFLICT_KEYS[kind]
    values = convert.record_values(record, kind)
    stmt = insert(RECORD).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=list(columns),
        index_where=predicate,
        set_=_upsert_set(stmt, values),
    ).returning(
        RECORD.c.id,
        RECORD.c.previous_digest,
        literal_column("(xmax = 0)").label("created"),
    )
    row = session.execute(stmt).one()
    created = bool(row.created)
    return UpsertResult(
        id=row.id,
        created=created,
        digest_changed=not created and old_digest != record.digest,
        previous_digest=row.previous_digest,
    )


def create_candidate(session: Session, record: RecordWrite) -> UpsertResult:
    """
    Insert a candidate row only if its key is free.

    :param session: Unit-of-work session.
    :param record: Row content.
    :returns: The outcome.
    :raises CandidateExistsError: If the candidate exists.
    """
    columns, predicate = _CONFLICT_KEYS[RecordState.CANDIDATE]
    stmt = (
        insert(RECORD)
        .values(convert.record_values(record, RecordState.CANDIDATE))
        .on_conflict_do_nothing(
            index_elements=list(columns), index_where=predicate
        )
        .returning(RECORD.c.id)
    )
    record_id = session.execute(stmt).scalar_one_or_none()
    if record_id is None:
        raise CandidateExistsError(
            f"candidate {record.identity} on ref {record.ref!r} exists"
        )
    return UpsertResult(
        id=record_id, created=True, digest_changed=False, previous_digest=None
    )


def get_record(session: Session, record_id: uuid.UUID) -> StoredRecord | None:
    """
    Fetch one record row.

    :param session: Unit-of-work session.
    :param record_id: Record id.
    :returns: The row, or ``None``.
    """
    row = (
        session.execute(select(RECORD).where(RECORD.c.id == record_id))
        .mappings()
        .first()
    )
    return None if row is None else convert.stored_record(row)


def list_change_tokens(
    session: Session, source_id: str, project: str | None
) -> list[ChangeTokenEntry]:
    """
    List the stored change state of published files.

    :param session: Unit-of-work session.
    :param source_id: Registration id.
    :param project: Restrict to one project, or ``None``.
    :returns: Entries ordered by project and path.
    """
    stmt = select(
        RECORD.c.id,
        RECORD.c.project,
        RECORD.c.path,
        RECORD.c.change_token,
        RECORD.c.digest,
    ).where(
        RECORD.c.kind == RecordState.PUBLISHED.value,
        RECORD.c.source_id == source_id,
    )
    if project is not None:
        stmt = stmt.where(RECORD.c.project == project)
    rows = session.execute(stmt.order_by(RECORD.c.project, RECORD.c.path))
    return [ChangeTokenEntry(**row) for row in rows.mappings()]


def delete_published(
    session: Session, record_ids: Collection[uuid.UUID]
) -> int:
    """
    Delete published rows by id; candidates are never deleted here.

    :param session: Unit-of-work session.
    :param record_ids: Ids to delete.
    :returns: Number of deleted rows.
    """
    if not record_ids:
        return 0
    stmt = (
        delete(RECORD)
        .where(
            RECORD.c.kind == RecordState.PUBLISHED.value,
            RECORD.c.id.in_(list(record_ids)),
        )
        .returning(RECORD.c.id)
    )
    return len(session.execute(stmt).all())


def list_identity_siblings(
    session: Session, identity: Identity
) -> list[StoredRecord]:
    """
    List every row of an identity.

    :param session: Unit-of-work session.
    :param identity: Logical identity.
    :returns: Published rows first, then by ref and path.
    """
    stmt = (
        select(RECORD)
        .where(
            RECORD.c.source_id == identity.source_id,
            RECORD.c.project == identity.project,
            RECORD.c.record_key == identity.record_key,
        )
        .order_by(
            (RECORD.c.kind != RecordState.PUBLISHED.value),
            RECORD.c.ref,
            RECORD.c.path,
        )
    )
    rows = session.execute(stmt).mappings()
    return [convert.stored_record(row) for row in rows]


#: Columns needed to build a :class:`RecordSummary` (shared by
#: :func:`list_relationship_summaries` and
#: :func:`list_relationship_candidates`).
_SUMMARY_COLUMNS = (
    RECORD.c.id,
    RECORD.c.source_id,
    RECORD.c.project,
    RECORD.c.record_key,
    RECORD.c.adr_uuid,
    RECORD.c.links,
    RECORD.c.record_kind,
    RECORD.c.path,
    RECORD.c.kind,
    RECORD.c.updated_at,
)


def _to_summary(row: Any) -> RecordSummary:
    """
    Build a :class:`RecordSummary` from one ``_SUMMARY_COLUMNS`` row.

    :param row: A mapping of ``_SUMMARY_COLUMNS``.
    :returns: The summary, keyed by ``str(record id)``.
    """
    return RecordSummary(
        key=str(row["id"]),
        identity=Identity(row["source_id"], row["project"], row["record_key"]),
        adr_uuid=row["adr_uuid"],
        links=Links.from_dict(row["links"]),
        record_kind=RecordKind(row["record_kind"]),
        path=row["path"],
        published=row["kind"] == RecordState.PUBLISHED.value,
        updated_at=row["updated_at"],
    )


def list_relationship_summaries(
    session: Session, kind: RecordState | None
) -> list[RecordSummary]:
    """
    List relationship summaries keyed by ``str(record id)``.

    :param session: Unit-of-work session.
    :param kind: Restrict to one state, or ``None`` for all rows.
    :returns: One summary per row, ordered by identity and path.
    """
    stmt = select(*_SUMMARY_COLUMNS)
    if kind is not None:
        stmt = stmt.where(RECORD.c.kind == kind.value)
    stmt = stmt.order_by(
        RECORD.c.source_id, RECORD.c.project, RECORD.c.path, RECORD.c.id
    )
    return [_to_summary(row) for row in session.execute(stmt).mappings()]


def list_relationship_candidates(
    session: Session,
    self_uuid: uuid.UUID,
    link_targets: Collection[uuid.UUID],
) -> list[RecordSummary]:
    """
    List the published rows that can affect one record's relationships.

    A bounded alternative to ``list_relationship_summaries(PUBLISHED)``
    for one detail request: instead of every published row, this
    returns only rows that :class:`~app.domain.relationships.
    RelationshipIndex` could possibly use to resolve *self_uuid*'s
    relationships --

    - other rows sharing *self_uuid* (duplicate-identity detection);
    - rows whose ``adr_uuid`` is one of *link_targets* (candidates for
      resolving *self_uuid*'s own outbound links, with every row
      sharing a target so ambiguity still resolves correctly);
    - rows that link to *self_uuid* via ``updates``, ``obsoletes`` or
      ``corrects`` (inbound links and errata).

    The Postgres planner still scans every published row (``links``
    has no index), but only the rows that match are sent to the
    client and turned into :class:`RecordSummary` objects, which is
    where the cost of :func:`list_relationship_summaries` actually
    goes at catalog scale (see
    ``docs/developer/performance.rst``). The result, combined with
    :meth:`~app.storage.port.CatalogStore.list_identity_siblings`, is
    exactly the summary set :func:`list_relationship_summaries` would
    have narrowed :class:`RelationshipIndex` to for this one record's
    :meth:`~app.domain.relationships.RelationshipIndex.view`.

    :param session: Unit-of-work session.
    :param self_uuid: The viewed record's own UUID.
    :param link_targets: UUIDs the viewed record's own ``updates``,
        ``obsoletes`` and ``corrects`` links target.
    :returns: The matching published rows, ordered by identity and
        path.
    """
    uuids = {self_uuid, *link_targets}
    target = str(self_uuid)
    stmt = (
        select(*_SUMMARY_COLUMNS)
        .where(
            RECORD.c.kind == RecordState.PUBLISHED.value,
            or_(
                RECORD.c.adr_uuid.in_(uuids),
                RECORD.c.links["updates"].op("?")(target),
                RECORD.c.links["obsoletes"].op("?")(target),
                RECORD.c.links["corrects"].astext == target,
            ),
        )
        .order_by(
            RECORD.c.source_id, RECORD.c.project, RECORD.c.path, RECORD.c.id
        )
    )
    return [_to_summary(row) for row in session.execute(stmt).mappings()]


def list_facets(session: Session) -> list[FacetEntry]:
    """
    Count decision rows per ``(source_id, project)``, for filter UIs.

    Errata are not counted, matching the default search.

    :param session: Unit-of-work session.
    :returns: One entry per pair, ordered by source id then project.
    """
    stmt = (
        select(
            RECORD.c.source_id,
            RECORD.c.project,
            func.count().label("count"),
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
