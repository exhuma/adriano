"""
The shared ingest path used by poll and push intake.

One document goes through exactly these steps, whoever delivered it:

1. parse and validate (:func:`app.domain.records.parse_record`);
2. compute the canonical digest (:func:`app.domain.hashing.content_digest`)
   -- any client-supplied digest is ignored;
3. store the immutable snapshot (``put_revision``) of the canonical text;
4. render the Markdown body (and, for an erratum, its original,
   corrected and notes sections) with markdown-it-py and sanitize the
   HTML with nh3;
5. upsert the published row, or the candidate row (replace or
   create-only), with its per-record validation issues.

:func:`prepare_document` (steps 1, 2 and 4) is pure, so push intake can
inspect the result (e.g. compare the document UUID with the request)
before writing anything; :func:`ingest_document` adds steps 3 and 5.

Ingest never touches ``decision_event``: approval history is keyed by
identity and digest and is never rewritten by intake. Callers run ingest
inside :meth:`~app.storage.port.CatalogStoreProvider.lock_registration`.

Relationship issues (``missing_target``, ``ambiguous_target``,
``duplicate_uuid``) are **not** stored by ingest. They depend on other
records -- also those of other registrations, which can change without
this record changing -- so they are computed at read time from
:meth:`~app.storage.port.CatalogStore.list_relationship_summaries` with
:class:`app.domain.relationships.RelationshipIndex` (phase 05, catalog
service). Stored ``issues`` therefore hold only the per-document
findings of :func:`~app.domain.records.parse_record`.

Public API: :class:`IncomingDocument`, :class:`PreparedDocument`,
:class:`IngestResult`, :func:`render_markdown`,
:func:`render_erratum`, :func:`prepare_document`, :func:`ingest_document`.
"""

import uuid
from dataclasses import dataclass

import nh3
from markdown_it import MarkdownIt

from app.domain.errata import ErratumContent
from app.domain.hashing import canonicalize, canonicalize_text, content_digest
from app.domain.issues import Issue
from app.domain.records import ParsedRecord, parse_record, record_key
from app.storage.port import (
    CatalogStore,
    RecordState,
    RecordWrite,
    StoredErratum,
)

_MARKDOWN = MarkdownIt("commonmark").enable(["table", "strikethrough"])


@dataclass(frozen=True, slots=True, kw_only=True)
class IncomingDocument:
    """
    One delivered document, independent of the intake path.

    :param source_id: Owning registration id.
    :param project: Owning project path.
    :param path: File path inside the project.
    :param ref: Branch/ref the content came from.
    :param content: The exact bytes fetched or pushed.
    :param change_token: Source change token (``None`` for pushes).
    :param source_url: Link to the file at the source, if any.
    :param author: Push or commit author, if known.
    """

    source_id: str
    project: str
    path: str
    ref: str
    content: bytes
    change_token: str | None = None
    source_url: str | None = None
    author: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PreparedDocument:
    """
    A parsed, hashed and rendered document, ready to be stored.

    :param parsed: Parse and validation result.
    :param digest: Canonical digest string.
    :param text: Canonical text stored as the revision snapshot.
    :param record: The row to write.
    """

    parsed: ParsedRecord
    digest: str
    text: str
    record: RecordWrite


@dataclass(frozen=True, slots=True, kw_only=True)
class IngestResult:
    """
    Outcome of ingesting one document.

    :param record_id: Stored row id.
    :param kind: Published or candidate.
    :param digest: Canonical digest string.
    :param created: ``True`` if a new row was inserted.
    :param digest_changed: ``True`` if an existing row got new content.
    :param previous_digest: Digest before this write, if any.
    :param record_key: Identity key of the row.
    :param issues: Per-document validation issues.
    """

    record_id: uuid.UUID
    kind: RecordState
    digest: str
    created: bool
    digest_changed: bool
    previous_digest: str | None
    record_key: str
    issues: tuple[Issue, ...]


def render_markdown(body: str) -> str:
    """
    Render a Markdown body to sanitized HTML.

    :param body: Markdown without frontmatter.
    :returns: HTML safe to embed (scripts, event handlers and unsafe URLs
        removed; links get ``rel="noopener noreferrer"``).
    """
    return nh3.clean(_MARKDOWN.render(body))


def render_erratum(content: ErratumContent | None) -> StoredErratum | None:
    """
    Render the sections of an erratum to sanitized HTML.

    :param content: Parsed erratum content, ``None`` for a decision.
    :returns: The content to store (missing optional sections stay
        ``None``), or ``None`` for a decision.
    """
    if content is None:
        return None
    original, notes = content.original, content.notes
    return StoredErratum(
        type=content.type,
        section=content.section,
        reported_by=content.reported_by,
        reported_date=content.reported_date,
        original_html=None if original is None else render_markdown(original),
        corrected_html=render_markdown(content.corrected),
        notes_html=None if notes is None else render_markdown(notes),
    )


def _canonical_text(raw: bytes) -> str:
    """
    Decode bytes to the canonical snapshot text.

    :param raw: The exact bytes.
    :returns: Canonical text; invalid UTF-8 is replaced by U+FFFD (such
        content carries a ``sha256-raw-v1`` digest and a
        ``bad_encoding`` issue).
    """
    try:
        return canonicalize(raw)
    except UnicodeDecodeError:
        return canonicalize_text(raw.decode("utf-8", errors="replace"))


def prepare_document(document: IncomingDocument) -> PreparedDocument:
    """
    Parse, validate, hash and render a document (pure).

    Never raises for content problems.

    :param document: The delivered document.
    :returns: The prepared document.
    """
    parsed = parse_record(document.content, filename=document.path)
    digest = str(content_digest(document.content))
    record = RecordWrite(
        source_id=document.source_id,
        project=document.project,
        path=document.path,
        ref=document.ref,
        adr_uuid=parsed.adr_uuid,
        record_key=record_key(
            parsed.adr_uuid, document.source_id, document.project, document.path
        ),
        digest=digest,
        change_token=document.change_token,
        metadata=parsed.metadata,
        title=parsed.title,
        title_source=parsed.title_source,
        decision_date=parsed.display_date,
        decision_date_inferred=parsed.decision_date_inferred,
        record_kind=parsed.record_kind,
        links=parsed.links,
        rendered_html=render_markdown(parsed.body),
        issues=parsed.issues,
        source_url=document.source_url,
        author=document.author,
        erratum=render_erratum(parsed.erratum),
    )
    return PreparedDocument(
        parsed=parsed,
        digest=digest,
        text=_canonical_text(document.content),
        record=record,
    )


def ingest_document(
    store: CatalogStore,
    prepared: PreparedDocument,
    kind: RecordState,
    *,
    create_only: bool = False,
) -> IngestResult:
    """
    Store the snapshot and upsert the row of a prepared document.

    :param store: Store of the caller's (locked) unit of work.
    :param prepared: Output of :func:`prepare_document`.
    :param kind: Published (poll) or candidate (push).
    :param create_only: Candidates only: refuse to replace an existing
        candidate (``POST`` semantics).
    :returns: The outcome.
    :raises app.errors.CandidateExistsError: If *create_only* and the
        candidate exists.
    """
    store.put_revision(prepared.digest, prepared.text)
    record = prepared.record
    if kind is RecordState.PUBLISHED:
        outcome = store.upsert_published(record)
    elif create_only:
        outcome = store.create_candidate(record)
    else:
        outcome = store.upsert_candidate(record)
    return IngestResult(
        record_id=outcome.id,
        kind=kind,
        digest=prepared.digest,
        created=outcome.created,
        digest_changed=outcome.digest_changed,
        previous_digest=outcome.previous_digest,
        record_key=record.record_key,
        issues=record.issues,
    )
