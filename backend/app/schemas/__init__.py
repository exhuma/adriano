"""
Pydantic response models for the read-only catalog HTTP API.

Every model declares ``model_config = ConfigDict(from_attributes=True)``
so routers build responses directly from the plain dataclasses returned
by :mod:`app.services.catalog` with ``SomeSchema.model_validate(value)``;
no router re-reads the storage port or domain modules directly.

Modules:

- :mod:`app.schemas.records` -- search results and the record detail
  page.
- :mod:`app.schemas.sources` -- source registrations and search facets.
"""

from app.schemas.records import (
    ApprovalOut,
    DecisionSummaryOut,
    ErratumOut,
    FreshnessOut,
    InboundLinkOut,
    IssueCountsOut,
    IssueOut,
    MetadataOut,
    OutboundLinkOut,
    PolicySummaryOut,
    ProvenanceOut,
    RecordDetailOut,
    SearchItemOut,
    SearchPageOut,
    SiblingOut,
)
from app.schemas.sources import (
    FacetProjectOut,
    FacetSourceOut,
    FacetsOut,
    SourceOut,
)

__all__ = [
    "ApprovalOut",
    "DecisionSummaryOut",
    "ErratumOut",
    "FacetProjectOut",
    "FacetSourceOut",
    "FacetsOut",
    "FreshnessOut",
    "InboundLinkOut",
    "IssueCountsOut",
    "IssueOut",
    "MetadataOut",
    "OutboundLinkOut",
    "PolicySummaryOut",
    "ProvenanceOut",
    "RecordDetailOut",
    "SearchItemOut",
    "SearchPageOut",
    "SiblingOut",
    "SourceOut",
]
