"""
SQLAlchemy ORM models of the PostgreSQL catalog store.

The schema is owned by the Alembic migrations (``alembic/versions``);
these classes only mirror it for querying and are never used to create
tables outside tests. Triggers (search vector, append-only decisions)
and column comments live in the migration only.

Public API: :class:`SourceRegistrationRow`, :class:`RevisionRow`,
:class:`RecordRow`, :class:`DecisionEventRow`, :class:`IntakeRunRow`.
"""

import datetime
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_UUID_DEFAULT = text("gen_random_uuid()")


def _now_column() -> Mapped[datetime.datetime]:
    """
    Build a non-null ``timestamptz`` column defaulting to ``now()``.

    :returns: The mapped column.
    """
    return mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SourceRegistrationRow(Base):
    """A source registration synced from ``catalog.yaml``."""

    __tablename__ = "source_registration"
    __table_args__ = (
        CheckConstraint(
            "last_status IN ('never', 'ok', 'partial', 'failed', 'disabled')",
            name="ck_source_registration_last_status",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[Any] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    config_error: Mapped[str | None] = mapped_column(Text)
    last_attempt_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_success_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="never"
    )
    last_error: Mapped[Any] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )


class RevisionRow(Base):
    """An immutable content-addressed snapshot."""

    __tablename__ = "revision"

    digest: Mapped[str] = mapped_column(Text, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = _now_column()


class RecordRow(Base):
    """A published or candidate ADR record."""

    __tablename__ = "record"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('published', 'candidate')", name="ck_record_kind"
        ),
        CheckConstraint(
            "title_source IN ('frontmatter', 'h1', 'filename')",
            name="ck_record_title_source",
        ),
        CheckConstraint(
            "record_kind IN ('decision', 'erratum')",
            name="ck_record_record_kind",
        ),
        Index(
            "uq_record_published_location",
            "source_id",
            "project",
            "path",
            unique=True,
            postgresql_where=text("kind = 'published'"),
        ),
        Index(
            "uq_record_candidate_identity_ref",
            "source_id",
            "project",
            "record_key",
            "ref",
            unique=True,
            postgresql_where=text("kind = 'candidate'"),
        ),
        Index("ix_record_identity", "source_id", "project", "record_key"),
        Index("ix_record_search", "search", postgresql_using="gin"),
        Index(
            "ix_record_links_corrects",
            text("(links ->> 'corrects')"),
            postgresql_where=text("(links ->> 'corrects') IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(
        Text, ForeignKey("source_registration.id"), nullable=False
    )
    project: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    ref: Mapped[str] = mapped_column(Text, nullable=False)
    adr_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    record_key: Mapped[str] = mapped_column(Text, nullable=False)
    digest: Mapped[str] = mapped_column(
        Text, ForeignKey("revision.digest"), nullable=False
    )
    previous_digest: Mapped[str | None] = mapped_column(
        Text, ForeignKey("revision.digest")
    )
    change_token: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[Any] = mapped_column("metadata", JSONB, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_source: Mapped[str] = mapped_column(Text, nullable=False)
    decision_date: Mapped[datetime.date | None] = mapped_column(Date)
    decision_date_inferred: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    record_kind: Mapped[str] = mapped_column(Text, nullable=False)
    links: Mapped[Any] = mapped_column(JSONB, nullable=False)
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    erratum: Mapped[Any] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    issues: Mapped[Any] = mapped_column(JSONB, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    search: Mapped[str] = mapped_column(TSVECTOR, nullable=False)
    first_seen_at: Mapped[datetime.datetime] = _now_column()
    updated_at: Mapped[datetime.datetime] = _now_column()
    last_seen_at: Mapped[datetime.datetime] = _now_column()


class DecisionEventRow(Base):
    """An append-only formal decision on one content digest."""

    __tablename__ = "decision_event"
    __table_args__ = (
        CheckConstraint(
            "action IN ('accepted', 'rejected')",
            name="ck_decision_event_action",
        ),
        UniqueConstraint(
            "source_id",
            "project",
            "record_key",
            "digest",
            name="uq_decision_event_identity_digest",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT
    )
    source_id: Mapped[str] = mapped_column(
        Text, ForeignKey("source_registration.id"), nullable=False
    )
    project: Mapped[str] = mapped_column(Text, nullable=False)
    record_key: Mapped[str] = mapped_column(Text, nullable=False)
    adr_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    digest: Mapped[str] = mapped_column(
        Text, ForeignKey("revision.digest"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor_issuer: Mapped[str] = mapped_column(Text, nullable=False)
    actor_subject: Mapped[str] = mapped_column(Text, nullable=False)
    actor_display: Mapped[str | None] = mapped_column(Text)
    actor_email: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    policy_id: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    provenance: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime.datetime] = _now_column()


class IntakeRunRow(Base):
    """One poll or push intake run."""

    __tablename__ = "intake_run"
    __table_args__ = (
        CheckConstraint("kind IN ('poll', 'push')", name="ck_intake_run_kind"),
        CheckConstraint(
            "status IN ('running', 'ok', 'partial', 'failed')",
            name="ck_intake_run_status",
        ),
        Index(
            "uq_intake_run_delivery",
            "source_id",
            "delivery_id",
            unique=True,
            postgresql_where=text("delivery_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT
    )
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    identity: Mapped[Any] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    delivery_id: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime.datetime] = _now_column()
    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    counts: Mapped[Any] = mapped_column(JSONB(none_as_null=True), nullable=True)
    errors: Mapped[Any] = mapped_column(JSONB(none_as_null=True), nullable=True)
