"""
Response models of the not-indexed list.

Built from the :mod:`app.services.not_indexed_view` dataclasses with
``model_validate`` (see :mod:`app.schemas`).
"""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.records import IssueOut
from app.storage.port import IntakeKind


class NotIndexedItemOut(BaseModel):
    """
    One document intake could not index, addressed by its location.

    ``holder_uuid`` is set for a duplicate UUID: the ADR that holds it
    (``/records/{holder_uuid}``).
    """

    model_config = ConfigDict(from_attributes=True)

    source_id: str
    project: str
    path: str
    ref: str
    origin: IntakeKind
    reasons: list[IssueOut]
    holder_uuid: uuid.UUID | None
    source_url: str | None
    first_seen_at: datetime.datetime
    last_seen_at: datetime.datetime
    has_content: bool


class NotIndexedPageOut(BaseModel):
    """One page of the not-indexed list."""

    model_config = ConfigDict(from_attributes=True)

    items: list[NotIndexedItemOut]
    total: int
    page: int
    page_size: int


class NotIndexedDetailOut(NotIndexedItemOut):
    """A not-indexed entry with the content intake rejected."""

    content: str | None
