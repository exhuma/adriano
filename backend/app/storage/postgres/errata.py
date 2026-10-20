"""
Erratum queries of the PostgreSQL store.

The reverse lookup "errata of one decision" filters on the expression
``(links ->> 'corrects')``, written with a literal key so it matches
the partial expression index ``ix_record_links_corrects`` (migration
``0003_erratum_content``) exactly. A bound key (SQLAlchemy's
``links["corrects"].astext``) would not match the index in a generic
plan.

Public API: :data:`CORRECTS_TARGET`, :func:`list_errata_for`.
"""

import uuid

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

from app.storage.port import ErratumRow, RecordState
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
