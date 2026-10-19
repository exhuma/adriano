"""
Response models for search results and the record detail page.

Field names match the :mod:`app.services.catalog` dataclasses they are
built from, so every model here reads straight off those dataclasses
through ``model_validate`` (``from_attributes=True``); none of this
module performs business logic.
"""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.domain.approval import ApprovalStateCode, DecisionAction, PolicyStatus
from app.domain.issues import IssueCode, Severity
from app.domain.relationships import DisplayStatus, InboundType, Resolution
from app.domain.values import LinkType, RecordKind, TitleSource
from app.storage.port import PollStatus, RecordState


class IssueOut(BaseModel):
    """One validation finding."""

    model_config = ConfigDict(from_attributes=True)

    severity: Severity
    code: IssueCode
    message: str


class IssueCountsOut(BaseModel):
    """Stored-issue counts of one record, by severity."""

    model_config = ConfigDict(from_attributes=True)

    error: int
    warning: int


class SearchItemOut(BaseModel):
    """One search result row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_id: str
    project: str
    path: str
    ref: str
    kind: RecordState
    record_kind: RecordKind
    approval_state: ApprovalStateCode
    issue_counts: IssueCountsOut


class SearchPageOut(BaseModel):
    """One page of search results."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SearchItemOut]
    total: int
    page: int
    page_size: int


class MetadataOut(BaseModel):
    """Identity and authored metadata of one record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    adr_uuid: uuid.UUID | None
    decision_date: datetime.date | None
    decision_date_inferred: bool
    kind: RecordState
    record_kind: RecordKind
    title: str
    title_source: TitleSource


class ProvenanceOut(BaseModel):
    """Where a record's content came from."""

    model_config = ConfigDict(from_attributes=True)

    source_id: str
    project: str
    path: str
    ref: str
    source_url: str | None


class FreshnessOut(BaseModel):
    """Freshness of a record's owning registration."""

    model_config = ConfigDict(from_attributes=True)

    last_attempt_at: datetime.datetime | None
    last_success_at: datetime.datetime | None
    last_status: PollStatus
    stale: bool


class OutboundLinkOut(BaseModel):
    """One outbound link and how it resolved."""

    model_config = ConfigDict(from_attributes=True)

    link_type: LinkType
    target_uuid: uuid.UUID
    target_id: uuid.UUID | None
    target_title: str | None
    resolution: Resolution | None
    ambiguous: bool
    candidate_ids: list[uuid.UUID]


class InboundLinkOut(BaseModel):
    """A link from another record to the one being viewed."""

    model_config = ConfigDict(from_attributes=True)

    link_type: InboundType
    source_id: uuid.UUID
    source_title: str


class ErratumOut(BaseModel):
    """One erratum record correcting the record being viewed."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str


class SiblingOut(BaseModel):
    """One published or candidate row sharing a record's identity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: RecordState
    source_id: str
    project: str
    path: str
    ref: str
    digest: str
    title: str
    decision_date: datetime.date | None
    decision_date_inferred: bool
    approval_state: ApprovalStateCode


class PolicySummaryOut(BaseModel):
    """The applicable approval policy, or why there is none."""

    model_config = ConfigDict(from_attributes=True)

    status: PolicyStatus
    id: str | None
    version: int | None
    required: bool | None


class DecisionSummaryOut(BaseModel):
    """One historical decision event, read-only in phase 05."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    digest: str
    action: DecisionAction
    actor_display: str | None
    comment: str | None
    created_at: datetime.datetime


class ApprovalOut(BaseModel):
    """Approval state of a record's current content."""

    model_config = ConfigDict(from_attributes=True)

    state: ApprovalStateCode
    needs_approval: bool
    policy: PolicySummaryOut
    history: list[DecisionSummaryOut]


class RecordDetailOut(BaseModel):
    """Everything the record detail page shows."""

    model_config = ConfigDict(from_attributes=True)

    metadata: MetadataOut
    issues: list[IssueOut]
    rendered_html: str
    provenance: ProvenanceOut
    freshness: FreshnessOut
    outbound_links: list[OutboundLinkOut]
    inbound_links: list[InboundLinkOut]
    errata: list[ErratumOut]
    status: DisplayStatus
    siblings: list[SiblingOut]
    legacy_signoff_unverified: list[str]
    approval: ApprovalOut
