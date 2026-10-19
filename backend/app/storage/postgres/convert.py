"""
Conversions between database rows and storage-port value types.

Rows are read with Core ``select()`` over the mapped tables, so every
function here takes a :class:`~sqlalchemy.engine.RowMapping` keyed by
column name and returns a port value type.

Public API: :func:`record_values`, :func:`stored_record`,
:func:`search_item`, :func:`registration`, :func:`revision`,
:func:`decision_event`, :func:`intake_run`.
"""

from typing import Any

from sqlalchemy.engine import RowMapping

from app.domain.approval import ApprovalStateCode, DecisionAction
from app.domain.issues import Issue
from app.domain.values import Identity, Links, RecordKind, TitleSource
from app.storage.port import (
    DecisionEvent,
    IntakeKind,
    IntakeRun,
    IntakeStatus,
    PollStatus,
    RecordState,
    RecordWrite,
    Registration,
    Revision,
    SearchItem,
    StoredRecord,
)


def record_values(record: RecordWrite, kind: RecordState) -> dict[str, Any]:
    """
    Build the ``record`` column values for an insert.

    :param record: Row content.
    :param kind: Published or candidate.
    :returns: Column name -> value, JSON columns as plain structures.
    """
    return {
        "kind": kind.value,
        "source_id": record.source_id,
        "project": record.project,
        "path": record.path,
        "ref": record.ref,
        "adr_uuid": record.adr_uuid,
        "record_key": record.record_key,
        "digest": record.digest,
        "change_token": record.change_token,
        "metadata": dict(record.metadata),
        "title": record.title,
        "title_source": record.title_source.value,
        "decision_date": record.decision_date,
        "decision_date_inferred": record.decision_date_inferred,
        "record_kind": record.record_kind.value,
        "links": record.links.to_dict(),
        "rendered_html": record.rendered_html,
        "issues": [issue.to_dict() for issue in record.issues],
        "source_url": record.source_url,
        "author": record.author,
    }


def _issues(raw: list[dict[str, str]]) -> tuple[Issue, ...]:
    """
    Rebuild stored issues.

    :param raw: Stored JSON list.
    :returns: The issues.
    """
    return tuple(Issue.from_dict(item) for item in raw)


def stored_record(row: RowMapping) -> StoredRecord:
    """
    Convert a full ``record`` row.

    :param row: Row with every ``record`` column.
    :returns: The stored record.
    """
    return StoredRecord(
        id=row["id"],
        kind=RecordState(row["kind"]),
        source_id=row["source_id"],
        project=row["project"],
        path=row["path"],
        ref=row["ref"],
        adr_uuid=row["adr_uuid"],
        record_key=row["record_key"],
        digest=row["digest"],
        previous_digest=row["previous_digest"],
        change_token=row["change_token"],
        metadata=row["metadata"],
        title=row["title"],
        title_source=TitleSource(row["title_source"]),
        decision_date=row["decision_date"],
        decision_date_inferred=row["decision_date_inferred"],
        record_kind=RecordKind(row["record_kind"]),
        links=Links.from_dict(row["links"]),
        rendered_html=row["rendered_html"],
        issues=_issues(row["issues"]),
        source_url=row["source_url"],
        author=row["author"],
        first_seen_at=row["first_seen_at"],
        updated_at=row["updated_at"],
        last_seen_at=row["last_seen_at"],
    )


def search_item(row: RowMapping) -> SearchItem:
    """
    Convert a search result row.

    :param row: Row with the search columns and ``approval_state``.
    :returns: The search item.
    """
    return SearchItem(
        id=row["id"],
        kind=RecordState(row["kind"]),
        source_id=row["source_id"],
        project=row["project"],
        path=row["path"],
        ref=row["ref"],
        adr_uuid=row["adr_uuid"],
        record_key=row["record_key"],
        digest=row["digest"],
        title=row["title"],
        record_kind=RecordKind(row["record_kind"]),
        decision_date=row["decision_date"],
        decision_date_inferred=row["decision_date_inferred"],
        issues=_issues(row["issues"]),
        approval_state=ApprovalStateCode(row["approval_state"]),
    )


def registration(row: RowMapping) -> Registration:
    """
    Convert a ``source_registration`` row.

    :param row: The row.
    :returns: The registration.
    """
    return Registration(
        id=row["id"],
        type=row["type"],
        config=row["config"],
        enabled=row["enabled"],
        config_error=row["config_error"],
        last_attempt_at=row["last_attempt_at"],
        last_success_at=row["last_success_at"],
        last_status=PollStatus(row["last_status"]),
        last_error=row["last_error"],
    )


def revision(row: RowMapping) -> Revision:
    """
    Convert a ``revision`` row.

    :param row: The row.
    :returns: The snapshot.
    """
    return Revision(
        digest=row["digest"],
        content=row["content"],
        created_at=row["created_at"],
    )


def decision_event(row: RowMapping) -> DecisionEvent:
    """
    Convert a ``decision_event`` row.

    :param row: The row.
    :returns: The event.
    """
    return DecisionEvent(
        id=row["id"],
        identity=Identity(row["source_id"], row["project"], row["record_key"]),
        adr_uuid=row["adr_uuid"],
        digest=row["digest"],
        action=DecisionAction(row["action"]),
        actor_issuer=row["actor_issuer"],
        actor_subject=row["actor_subject"],
        actor_display=row["actor_display"],
        actor_email=row["actor_email"],
        comment=row["comment"],
        policy_id=row["policy_id"],
        policy_version=row["policy_version"],
        provenance=row["provenance"],
        created_at=row["created_at"],
    )


def intake_run(row: RowMapping) -> IntakeRun:
    """
    Convert an ``intake_run`` row.

    :param row: The row.
    :returns: The run.
    """
    return IntakeRun(
        id=row["id"],
        source_id=row["source_id"],
        kind=IntakeKind(row["kind"]),
        identity=row["identity"],
        delivery_id=row["delivery_id"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        status=IntakeStatus(row["status"]),
        counts=row["counts"],
        errors=row["errors"],
    )
