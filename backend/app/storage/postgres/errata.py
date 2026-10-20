"""
Erratum queries of the PostgreSQL store.

The reverse lookup "errata of one decision" filters on the expression
``(links ->> 'corrects')``, written with a literal key so it matches
the partial expression index ``ix_record_links_corrects`` (migration
``0003_erratum_content``) exactly. A bound key (SQLAlchemy's
``links["corrects"].astext``) would not match the index in a generic
plan.

The title lookup for erratum search hits
(:func:`list_published_by_uuid`) returns only published rows: a link
resolves against published rows (plus the linking record's own
identity, which never applies to a decision an erratum corrects), see
:mod:`app.services.record_relationships`.

Public API: :data:`CORRECTS_TARGET`, :func:`list_errata_for`,
:func:`list_published_by_uuid`.
"""

import uuid
from collections.abc import Collection

from sqlalchemy import (
    ColumnElement,
    Table,
    Text,
    literal,
    literal_column,
    select,
    text,
)
from sqlalchemy.orm import Session

from app.domain.relationships import RecordSummary
from app.domain.values import Identity, Links, RecordKind
from app.storage.port import ErratumRow, LinkTarget, RecordState
from app.storage.postgres import convert
from app.storage.postgres.models import RecordRow

RECORD: Table = RecordRow.__table__  # type: ignore[assignment]

#: ``(links ->> 'corrects')``: the corrected decision's UUID as text,
#: identical to the expression of ``ix_record_links_corrects``.
CORRECTS_TARGET: ColumnElement[str] = RECORD.c.links.op(
    "->>", return_type=Text
)(literal_column("'corrects'"))

_ERRATUM_COLUMNS = (
    RECORD.c.id,
    RECORD.c.kind,
    RECORD.c.source_id,
    RECORD.c.project,
    RECORD.c.path,
    RECORD.c.ref,
    RECORD.c.adr_uuid,
    RECORD.c.record_key,
    RECORD.c.digest,
    RECORD.c.title,
    RECORD.c.erratum,
    RECORD.c.updated_at,
    RECORD.c.issues,
)


def list_errata_for(
    session: Session, target_uuid: uuid.UUID
) -> list[ErratumRow]:
    """
    List published and candidate errata that correct one decision UUID.

    :param session: Unit-of-work session.
    :param target_uuid: UUID of the corrected decision.
    :returns: Published rows first, then by source, project, path, ref
        and id.
    """
    stmt = (
        select(*_ERRATUM_COLUMNS)
        .where(
            CORRECTS_TARGET == literal(str(target_uuid), Text),
            text("record_kind = 'erratum'"),
        )
        .order_by(
            RECORD.c.kind != RecordState.PUBLISHED.value,
            RECORD.c.source_id,
            RECORD.c.project,
            RECORD.c.path,
            RECORD.c.ref,
            RECORD.c.id,
        )
    )
    rows = session.execute(stmt).mappings()
    return [convert.erratum_row(row) for row in rows]


def list_published_by_uuid(
    session: Session, uuids: Collection[uuid.UUID]
) -> list[LinkTarget]:
    """
    List the published rows holding any of *uuids*, with their titles.

    :param session: Unit-of-work session.
    :param uuids: Authored UUIDs; empty means no query.
    :returns: One entry per matching published row, ordered by id.
    """
    if not uuids:
        return []
    stmt = (
        select(
            RECORD.c.id,
            RECORD.c.source_id,
            RECORD.c.project,
            RECORD.c.record_key,
            RECORD.c.adr_uuid,
            RECORD.c.links,
            RECORD.c.record_kind,
            RECORD.c.path,
            RECORD.c.updated_at,
            RECORD.c.title,
        )
        .where(
            RECORD.c.kind == RecordState.PUBLISHED.value,
            RECORD.c.adr_uuid.in_(list(uuids)),
        )
        .order_by(RECORD.c.id)
    )
    return [
        LinkTarget(
            summary=RecordSummary(
                key=str(row["id"]),
                identity=Identity(
                    row["source_id"], row["project"], row["record_key"]
                ),
                adr_uuid=row["adr_uuid"],
                links=Links.from_dict(row["links"]),
                record_kind=RecordKind(row["record_kind"]),
                path=row["path"],
                published=True,
                updated_at=row["updated_at"],
            ),
            title=row["title"],
        )
        for row in session.execute(stmt).mappings()
    ]
