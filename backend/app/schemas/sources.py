"""
Response models for source registrations and search facets.

Field names match the :mod:`app.services.sources_view` dataclasses
they are built from (``from_attributes=True``); see :mod:`app.schemas` for the
convention.
"""

import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.frontmatter import JsonValue
from app.sources.port import ConfigErrorCode
from app.storage.port import IntakeKind, PollStatus


class SourceOut(BaseModel):
    """One source registration's configuration and freshness."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    enabled: bool
    config_error: str | None
    config_error_code: ConfigErrorCode | None
    intake: list[IntakeKind]
    published_ref: str
    last_attempt_at: datetime.datetime | None
    last_success_at: datetime.datetime | None
    last_status: PollStatus
    last_error: JsonValue
    stale: bool


class FacetProjectOut(BaseModel):
    """Record count of one project within a source."""

    model_config = ConfigDict(from_attributes=True)

    project: str
    count: int


class FacetSourceOut(BaseModel):
    """One source's projects, for the filter select."""

    model_config = ConfigDict(from_attributes=True)

    source_id: str
    count: int
    projects: list[FacetProjectOut]


class FacetsOut(BaseModel):
    """Filter options for the search UI."""

    model_config = ConfigDict(from_attributes=True)

    sources: list[FacetSourceOut]
