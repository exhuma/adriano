"""
Value types of intake runs, crossing the storage port.

Plain frozen dataclasses, independent of any ORM; kept apart from
:mod:`app.storage.values` only to keep modules small. Import them
through :mod:`app.storage.port`, which re-exports them.

Public API: :class:`IntakeRun`.
"""

import datetime
import uuid
from dataclasses import dataclass

from app.domain.frontmatter import JsonValue
from app.storage.values import IntakeKind, IntakeStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class IntakeRun:
    """
    One poll or push intake run.

    :param id: Run id.
    :param source_id: Registration id as requested.
    :param kind: Poll or push.
    :param identity: Who triggered the run (no secrets).
    :param delivery_id: Client-supplied push delivery id, if any.
    :param started_at: Start time.
    :param finished_at: End time, ``None`` while running.
    :param status: Run status.
    :param counts: Outcome counters.
    :param errors: Error details.
    """

    id: uuid.UUID
    source_id: str
    kind: IntakeKind
    identity: JsonValue
    delivery_id: str | None
    started_at: datetime.datetime
    finished_at: datetime.datetime | None
    status: IntakeStatus
    counts: JsonValue
    errors: JsonValue
