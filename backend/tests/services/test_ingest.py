"""Tests for the shared ingest path."""

import datetime
import uuid

import pytest
from sqlalchemy import Engine, text

from app.domain.errata import ErratumType
from app.domain.hashing import content_digest
from app.domain.issues import IssueCode
from app.errors import CandidateExistsError
from app.services.ingest import (
    IncomingDocument,
    ingest_document,
    prepare_document,
    render_markdown,
)
from app.storage.port import RecordState
from app.storage.postgres.store import PostgresStoreProvider

ADR_UUID = uuid.UUID("0b0c2f4e-1a2b-4c3d-8e9f-001122334455")
PATH = "doc/decisions/2024-12-24-use-postgresql.md"


def incoming(content: bytes, *, ref: str = "main") -> IncomingDocument:
    """
    Build an incoming document of the ``central`` registration.

    :param content: File bytes.
    :param ref: Ref.
    :returns: The document.
    """
    return IncomingDocument(
        source_id="central",
        project="platform",
        path=PATH,
        ref=ref,
        content=content,
        change_token="1:1",
    )


def adr(body: str = "Body.") -> bytes:
    """
    Build a valid ADR document.

    :param body: Markdown body.
    :returns: The bytes.
    """
    return (
        f"---\nuuid: {ADR_UUID}\ntitle: Use PostgreSQL\n"
        f"decision-date: 2024-12-24\n---\n{body}\n"
    ).encode()


def test_render_markdown_sanitizes_html() -> None:
    """Ensure scripts, handlers and javascript URLs are removed."""
    html = render_markdown(
        "# T\n\n<script>alert(1)</script>\n\n"
        '<a href="javascript:x" onclick="y">a</a> [b](https://e.org)\n\n'
        "| a | b |\n|---|---|\n| 1 | 2 |\n"
    )

    assert "<script" not in html
    assert "onclick" not in html
    assert "javascript:" not in html
    assert '<a href="https://e.org" rel="noopener noreferrer">b</a>' in html
    assert "<table>" in html


def test_prepare_document_parses_hashes_and_renders() -> None:
    """Ensure prepare yields the server digest and a full record write."""
    prepared = prepare_document(incoming(adr("Some *text*.")))

    assert prepared.digest == str(content_digest(adr("Some *text*.")))
    record = prepared.record
    assert record.adr_uuid == ADR_UUID
    assert record.record_key == str(ADR_UUID)
    assert record.title == "Use PostgreSQL"
    assert record.decision_date is not None
    assert not record.decision_date_inferred
    assert "<em>text</em>" in record.rendered_html
    assert "uuid:" not in record.rendered_html
    assert record.issues == ()


def test_prepare_document_is_line_ending_independent() -> None:
    """Ensure CRLF content hashes like LF content and stores LF text."""
    lf = prepare_document(incoming(adr()))
    crlf = prepare_document(incoming(adr().replace(b"\n", b"\r\n")))

    assert crlf.digest == lf.digest
    assert crlf.text == lf.text
    assert "\r" not in crlf.text


def test_prepare_document_keeps_bad_records() -> None:
    """Ensure broken documents are prepared with issues, never raised."""
    no_uuid = prepare_document(incoming(b"# Just a heading\n"))
    bad_bytes = prepare_document(incoming(adr() + b"\xff"))

    assert no_uuid.record.adr_uuid is None
    assert no_uuid.record.record_key.startswith("src:central/platform/")
    assert {i.code for i in no_uuid.record.issues} == {
        IssueCode.MISSING_FRONTMATTER
    }
    assert bad_bytes.digest.startswith("sha256-raw-v1:")
    assert "�" in bad_bytes.text
    assert IssueCode.BAD_ENCODING in {i.code for i in bad_bytes.record.issues}


def test_ingest_published_upserts_and_stores_the_snapshot(
    provider: PostgresStoreProvider, engine: Engine
) -> None:
    """Ensure ingest stores the revision and upserts without decisions."""
    first = prepare_document(incoming(adr("One.")))
    second = prepare_document(incoming(adr("Two.")))

    with provider.lock_registration("central") as store:
        created = ingest_document(store, first, RecordState.PUBLISHED)
        same = ingest_document(store, first, RecordState.PUBLISHED)
        changed = ingest_document(store, second, RecordState.PUBLISHED)
        revision = store.get_revision(first.digest)
        row = store.get_record(created.record_id)

    assert created.created and not same.created and not same.digest_changed
    assert changed.digest_changed
    assert changed.previous_digest == first.digest
    assert revision is not None and revision.content == first.text
    assert row is not None and row.digest == second.digest
    with engine.connect() as connection:
        events = connection.execute(
            text("SELECT count(*) FROM decision_event")
        ).scalar_one()
    assert events == 0


def test_ingest_candidate_create_only_conflicts(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure create-only candidates conflict and replace mode does not."""
    prepared = prepare_document(incoming(adr(), ref="feature"))

    with provider.lock_registration("central") as store:
        first = ingest_document(
            store, prepared, RecordState.CANDIDATE, create_only=True
        )
        again = ingest_document(store, prepared, RecordState.CANDIDATE)
        with pytest.raises(CandidateExistsError):
            ingest_document(
                store, prepared, RecordState.CANDIDATE, create_only=True
            )

    assert first.created and first.kind is RecordState.CANDIDATE
    assert again.record_id == first.record_id


ERRATUM_UUID = uuid.UUID("7c1e0000-1a2b-4c3d-8e9f-001122334455")


def erratum(corrected: str) -> bytes:
    """
    Build a valid erratum of :data:`ADR_UUID`.

    :param corrected: Markdown of the "Corrected text" section.
    :returns: The bytes.
    """
    return (
        f"---\nuuid: {ERRATUM_UUID}\nerratum-for: {ADR_UUID}\n"
        "type: editorial\nsection: Decision\nreported-by: alice\n"
        "date: 2025-05-01\n---\n## Original text\n\nUse *MySQL*.\n\n"
        f"## Corrected text\n\n{corrected}\n"
    ).encode()


def test_prepare_document_renders_sanitized_erratum_sections() -> None:
    """Ensure erratum sections are rendered and sanitized at ingest."""
    prepared = prepare_document(
        incoming(erratum("Use **PostgreSQL**.\n\n<script>alert(1)</script>"))
    )

    content = prepared.record.erratum
    assert content is not None
    assert content.type is ErratumType.EDITORIAL
    assert content.section == "Decision"
    assert content.reported_by == "alice"
    assert content.reported_date == datetime.date(2025, 5, 1)
    assert content.original_html == "<p>Use <em>MySQL</em>.</p>\n"
    assert "<strong>PostgreSQL</strong>" in content.corrected_html
    assert "<script" not in content.corrected_html
    assert "alert(1)" not in content.corrected_html
    assert content.notes_html is None


def test_prepare_document_has_no_erratum_for_decisions() -> None:
    """Ensure decisions carry no erratum content."""
    assert prepare_document(incoming(adr())).record.erratum is None


def test_ingest_stores_erratum_content(
    provider: PostgresStoreProvider,
) -> None:
    """Ensure the ingested erratum is found by the reverse lookup."""
    prepared = prepare_document(incoming(erratum("Fixed."), ref="fix"))

    with provider.lock_registration("central") as store:
        result = ingest_document(store, prepared, RecordState.CANDIDATE)
        rows = store.list_errata_for(ADR_UUID)

    assert [row.id for row in rows] == [result.record_id]
    assert rows[0].erratum == prepared.record.erratum
