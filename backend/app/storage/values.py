"""
Value types crossing the storage port.

Plain frozen dataclasses and enums, independent of any ORM. Import them
through :mod:`app.storage.port`, which re-exports everything here.

Public API:

- enums :class:`RecordState`, :class:`PollStatus`, :class:`IntakeKind`,
  :class:`IntakeStatus`; constant :data:`MAX_PAGE_SIZE`; alias
  :data:`JsonObject`
- values :class:`RegistrationConfig`, :class:`Registration`,
  :class:`Revision`, :class:`RecordWrite`, :class:`StoredRecord`,
  :class:`UpsertResult`, :class:`ChangeTokenEntry`,
  :class:`SearchFilters`, :class:`SearchItem`, :class:`SearchPage`,
  :class:`NewDecision`, :class:`DecisionEvent`, :class:`IntakeRun`
"""

import datetime
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.approval import (
    ApprovalStateCode,
    DecisionAction,
    DecisionEventView,
)
from app.domain.frontmatter import JsonValue
from app.domain.issues import Issue
from app.domain.values import Identity, Links, RecordKind, TitleSource

#: Upper bound for ``page_size`` in
#: :meth:`app.storage.port.CatalogStore.search`.
MAX_PAGE_SIZE = 50

type JsonObject = Mapping[str, JsonValue]


class RecordState(StrEnum):
    """Lifecycle state of a stored record row."""

    PUBLISHED = "published"
    CANDIDATE = "candidate"


class PollStatus(StrEnum):
    """Outcome of the latest poll of a registration."""

    NEVER = "never"
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    DISABLED = "disabled"


class IntakeKind(StrEnum):
    """How content entered the catalog."""

    POLL = "poll"
    PUSH = "push"


class IntakeStatus(StrEnum):
    """Status of one intake run."""

    RUNNING = "running"
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True, kw_only=True)
class RegistrationConfig:
    """
    One source registration as read from ``catalog.yaml``.

    :param id: Stable registration id.
    :param type: Source type (``filesystem`` or ``gitlab``).
    :param config: Type-specific settings, secrets excluded.
    :param enabled: ``False`` when the entry is invalid.
    :param config_error: Readable reason why the entry is invalid.
    """

    id: str
    type: str
    config: JsonObject
    enabled: bool = True
    config_error: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Registration:
    """
    A stored source registration with its poll status.

    :param id: Stable registration id.
    :param type: Source type.
    :param config: Type-specific settings, secrets excluded.
    :param enabled: Whether the registration may be polled / pushed to.
    :param config_error: Why the registration is disabled, if invalid.
    :param last_attempt_at: Start of the latest poll attempt.
    :param last_success_at: Start of the latest fully successful poll.
    :param last_status: Outcome of the latest poll.
    :param last_error: Error details of the latest poll, if any.
    """

    id: str
    type: str
    config: JsonObject
    enabled: bool
    config_error: str | None
    last_attempt_at: datetime.datetime | None
    last_success_at: datetime.datetime | None
    last_status: PollStatus
    last_error: JsonValue


@dataclass(frozen=True, slots=True, kw_only=True)
class Revision:
    """
    An immutable, content-addressed snapshot.

    :param digest: Digest string (``sha256-v1:...``).
    :param content: Canonical text content.
    :param created_at: When the snapshot was first stored.
    """

    digest: str
    content: str
    created_at: datetime.datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordWrite:
    """
    Everything ingest writes for one record row.

    The revision for :attr:`digest` must have been stored first
    (:meth:`app.storage.port.CatalogStore.put_revision`).

    :param source_id: Owning registration id.
    :param project: Owning project path.
    :param path: File path inside the project.
    :param ref: Branch/ref the content came from.
    :param adr_uuid: Authored UUID, ``None`` if missing or invalid.
    :param record_key: Identity key (:func:`app.domain.values.record_key`).
    :param digest: Digest string of the current content.
    :param change_token: Source change token (``None`` for pushes).
    :param metadata: Parsed frontmatter.
    :param title: Display title.
    :param title_source: Where the title came from.
    :param decision_date: Displayed decision date.
    :param decision_date_inferred: Whether the date is only inferred from
        the filename.
    :param record_kind: Decision or erratum.
    :param links: Validated outbound links.
    :param rendered_html: Sanitized HTML rendering of the body.
    :param issues: Validation issues.
    :param source_url: Link to the content at the source, if any.
    :param author: Push or commit author, if known.
    """

    source_id: str
    project: str
    path: str
    ref: str
    adr_uuid: uuid.UUID | None
    record_key: str
    digest: str
    change_token: str | None
    metadata: JsonObject
    title: str
    title_source: TitleSource
    decision_date: datetime.date | None
    decision_date_inferred: bool
    record_kind: RecordKind
    links: Links
    rendered_html: str
    issues: tuple[Issue, ...]
    source_url: str | None = None
    author: str | None = None

    @property
    def identity(self) -> Identity:
        """
        Logical identity of the record.

        :returns: ``(source_id, project, record_key)``.
        """
        return Identity(self.source_id, self.project, self.record_key)


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredRecord(RecordWrite):
    """
    A stored record row.

    :param id: Surrogate id used in URLs.
    :param kind: Published or candidate.
    :param previous_digest: Digest before the latest content change.
    :param first_seen_at: When the row was created.
    :param updated_at: When the content digest last changed.
    :param last_seen_at: When ingest last wrote the row.
    """

    id: uuid.UUID
    kind: RecordState
    previous_digest: str | None
    first_seen_at: datetime.datetime
    updated_at: datetime.datetime
    last_seen_at: datetime.datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class UpsertResult:
    """
    Outcome of a record upsert.

    :param id: Record id.
    :param created: ``True`` if a new row was inserted.
    :param digest_changed: ``True`` if an existing row got new content.
    :param previous_digest: The row's previous digest, if any.
    """

    id: uuid.UUID
    created: bool
    digest_changed: bool
    previous_digest: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeTokenEntry:
    """
    Stored change state of one published file.

    :param id: Record id.
    :param project: Owning project path.
    :param path: File path inside the project.
    :param change_token: Source change token, if known.
    :param digest: Current digest.
    """

    id: uuid.UUID
    project: str
    path: str
    change_token: str | None
    digest: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchFilters:
    """
    Search filters; ``None`` / ``False`` means "no filter".

    :param source_id: Registration id.
    :param project: Project path.
    :param kind: Published or candidate.
    :param needs_approval: Only records whose approval state needs
        approval (:func:`app.domain.approval.evaluate`).
    """

    source_id: str | None = None
    project: str | None = None
    kind: RecordState | None = None
    needs_approval: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchItem:
    """
    One search hit.

    :param id: Record id.
    :param kind: Published or candidate.
    :param source_id: Registration id.
    :param project: Project path.
    :param path: File path inside the project.
    :param ref: Branch/ref of the content.
    :param adr_uuid: Authored UUID, if valid.
    :param record_key: Identity key.
    :param digest: Current digest.
    :param title: Display title.
    :param record_kind: Decision or erratum.
    :param decision_date: Displayed decision date.
    :param decision_date_inferred: Whether the date is inferred.
    :param issues: Validation issues.
    :param approval_state: Approval state of the current digest, computed
        by the store with the same rules as
        :func:`app.domain.approval.evaluate`.
    """

    id: uuid.UUID
    kind: RecordState
    source_id: str
    project: str
    path: str
    ref: str
    adr_uuid: uuid.UUID | None
    record_key: str
    digest: str
    title: str
    record_kind: RecordKind
    decision_date: datetime.date | None
    decision_date_inferred: bool
    issues: tuple[Issue, ...]
    approval_state: ApprovalStateCode


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchPage:
    """
    One page of search results.

    :param items: Hits on this page.
    :param total: Number of hits over all pages.
    :param page: 1-based page number.
    :param page_size: Requested page size.
    """

    items: tuple[SearchItem, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True, slots=True, kw_only=True)
class NewDecision:
    """
    A decision to append.

    :param identity: Logical identity decided on.
    :param adr_uuid: The record UUID.
    :param digest: Digest of the decided content.
    :param action: Accepted or rejected.
    :param actor_issuer: Reviewer token issuer.
    :param actor_subject: Reviewer token subject.
    :param actor_display: Reviewer display name, if known.
    :param actor_email: Reviewer verified email, if known.
    :param comment: Optional reviewer comment.
    :param policy_id: Applied policy id.
    :param policy_version: Applied policy version.
    :param provenance: Record id, kind, ref, path and source URL at
        decision time.
    """

    identity: Identity
    adr_uuid: uuid.UUID
    digest: str
    action: DecisionAction
    actor_issuer: str
    actor_subject: str
    actor_display: str | None
    actor_email: str | None
    comment: str | None
    policy_id: str
    policy_version: int
    provenance: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionEvent(NewDecision):
    """
    A stored, append-only decision event.

    :param id: Stable event id.
    :param created_at: Server timestamp.
    """

    id: uuid.UUID
    created_at: datetime.datetime

    def as_view(self) -> DecisionEventView:
        """
        Convert to the domain view used by approval evaluation.

        :returns: The event view.
        """
        return DecisionEventView(
            id=str(self.id),
            digest=self.digest,
            action=self.action,
            created_at=self.created_at,
        )


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
