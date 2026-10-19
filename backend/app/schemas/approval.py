"""
Request/response models for decisions and CI candidate intake.

The candidate request body itself is
:class:`app.services.intake.CandidateSubmission` (the intake service
validates it after authenticating the push token); only its response
lives here.
"""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.domain.approval import DecisionAction
from app.schemas.records import IssueOut

#: Longest accepted reviewer comment.
MAX_COMMENT_LENGTH = 2000


class DecisionIn(BaseModel):
    """Body of ``POST /api/v1/records/{id}/decisions``."""

    model_config = ConfigDict(extra="forbid")

    action: DecisionAction
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)
    expected_digest: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Digest the reviewer saw; 409 `digest_changed` if the record's "
            "content changed since."
        ),
    )


class CandidateResultOut(BaseModel):
    """Outcome of ``PUT``/``POST /api/v1/candidates``."""

    model_config = ConfigDict(from_attributes=True)

    record_id: uuid.UUID
    digest: str
    created: bool
    updated: bool
    deduplicated: bool
    issues: list[IssueOut]
    catalog_path: str
