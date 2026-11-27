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

A document without a valid UUID has no identity: it is not a record.
:func:`prepare_document` then leaves :attr:`PreparedDocument.record`
empty and :func:`not_indexed_entry` describes it for the not-indexed
list instead (written with :func:`queue_document`).

:func:`prepare_document` (steps 1, 2 and 4) is pure, so intake can
inspect the result (e.g. compare the document UUID with the request,
or apply the UUID holder rule) before writing anything;
:func:`ingest_document` adds steps 3 and 5.

Ingest never touches ``decision_event``: approval history is keyed by
UUID and digest and is never rewritten by intake. Callers run ingest
inside :meth:`~app.storage.port.CatalogStoreProvider.lock_registration`.

Relationship issues (``missing_target``) are **not** stored by ingest.
They depend on other records, which can change without this record
changing, so they are computed at read time
(:mod:`app.services.record_relationships`). Stored ``issues`` hold only
the per-document findings of :func:`~app.domain.records.parse_record`.

Public API: :class:`IncomingDocument`, :class:`PreparedDocument`,
:class:`IngestResult`, :func:`render_markdown`,
:func:`render_erratum`, :func:`prepare_document`,
:func:`ingest_document`, :func:`not_indexed_entry`,
:func:`queue_document`.
"""

import uuid
from dataclasses import dataclass, replace

import nh3
from markdown_it import MarkdownIt

from app.domain.errata import ErratumContent
from app.domain.hashing import canonicalize, canonicalize_text, content_digest
from app.domain.issues import Issue
from app.domain.records import ParsedRecord, parse_record
from app.storage.port import (
    CatalogStore,
    IntakeKind,
    NotIndexedKey,
    NotIndexedWrite,
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

    @property
    def key(self) -> NotIndexedKey:
        """
        Where the document was found, as a not-indexed key.

        :returns: ``(source_id, project, path, ref)``.
        """
        return NotIndexedKey(self.source_id, self.project, self.path, self.ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class PreparedDocument:
    """
    A parsed, hashed and rendered document, ready to be stored.

    :param document: The delivered document, without its content.
    :param parsed: Parse and validation result.
    :param digest: Canonical digest string.
    :param text: Canonical text stored as the revision snapshot.
    :param record: The row to write; ``None`` when the document has no
        valid UUID (see :attr:`reasons`).
    """

    document: IncomingDocument
    parsed: ParsedRecord
    digest: str
    text: str
    record: RecordWrite | None

    @property
    def reasons(self) -> tuple[Issue, ...]:
        """
        Why the document cannot be indexed, if it cannot.

        :returns: The reasons, ``()`` when :attr:`record` is set.
        """
        return self.parsed.not_indexed_reasons


@dataclass(frozen=True, slots=True, kw_only=True)
class IngestResult:
    """
    Outcome of ingesting one document.

    :param adr_uuid: UUID of the stored ADR.
    :param ref: Ref of the stored row.
    :param kind: Published or candidate.
    :param digest: Canonical digest string.
    :param created: ``True`` if a new row was inserted.
    :param digest_changed: ``True`` if an existing row got new content.
    :param previous_digest: Digest before this write, if any.
    :param moved: ``True`` if a published row got a new location.
    :param issues: Per-document validation issues.
    """

    adr_uuid: uuid.UUID
    ref: str
    kind: RecordState
    digest: str
    created: bool
    digest_changed: bool
    previous_digest: str | None
    moved: bool
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


def _record(
    document: IncomingDocument, parsed: ParsedRecord, digest: str
) -> RecordWrite | None:
    """
    Build the row of a parsed document, if it has an identity.

    :param document: The delivered document.
    :param parsed: Its parse result.
    :param digest: Its canonical digest.
    :returns: The row, or ``None`` without a valid UUID.
    """
    if parsed.adr_uuid is None:
        return None
    return RecordWrite(
        source_id=document.source_id,
        project=document.project,
        path=document.path,
        ref=document.ref,
        adr_uuid=parsed.adr_uuid,
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


def prepare_document(document: IncomingDocument) -> PreparedDocument:
    """
    Parse, validate, hash and render a document (pure).

    Never raises for content problems.

    :param document: The delivered document.
    :returns: The prepared document (without a row when it has no
        valid UUID).
    """
    parsed = parse_record(document.content, filename=document.path)
    digest = str(content_digest(document.content))
    return PreparedDocument(
        document=replace(document, content=b""),
        parsed=parsed,
        digest=digest,
        text=_canonical_text(document.content),
        record=_record(document, parsed, digest),
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
    :raises ValueError: If the document has no row (no valid UUID).
    """
    record = prepared.record
    if record is None:
        raise ValueError(f"{prepared.document.key} has no valid UUID")
    store.put_revision(prepared.digest, prepared.text)
    if kind is RecordState.PUBLISHED:
        outcome = store.upsert_published(record)
    elif create_only:
        outcome = store.create_candidate(record)
    else:
        outcome = store.upsert_candidate(record)
    return IngestResult(
        adr_uuid=record.adr_uuid,
        ref=record.ref,
        kind=kind,
        digest=prepared.digest,
        created=outcome.created,
        digest_changed=outcome.digest_changed,
        previous_digest=outcome.previous_digest,
        moved=outcome.moved,
        issues=record.issues,
    )


def not_indexed_entry(
    prepared: PreparedDocument,
    origin: IntakeKind,
    *,
    reasons: tuple[Issue, ...] | None = None,
    holder_uuid: uuid.UUID | None = None,
) -> NotIndexedWrite:
    """
    Describe a prepared document for the not-indexed list.

    The change token is kept only when the content alone explains the
    entry: a losing duplicate (*holder_uuid*) depends on another file,
    so it gets no token and the next poll reads it again.

    :param prepared: The prepared document.
    :param origin: The intake that found it.
    :param reasons: Why it is not indexed; default
        :attr:`PreparedDocument.reasons`.
    :param holder_uuid: For a losing duplicate, the UUID it claims.
    :returns: The entry to write with :func:`queue_document`.
    """
    document = prepared.document
    return NotIndexedWrite(
        key=document.key,
        origin=origin,
        reasons=prepared.reasons if reasons is None else reasons,
        digest=prepared.digest,
        holder_uuid=holder_uuid,
        change_token=None if holder_uuid else document.change_token,
        source_url=document.source_url,
    )


def queue_document(
    store: CatalogStore, prepared: PreparedDocument, entry: NotIndexedWrite
) -> None:
    """
    Store the snapshot and the not-indexed entry of a document.

    The snapshot is kept so the list can show what was found.

    :param store: Store of the caller's (locked) unit of work.
    :param prepared: The prepared document.
    :param entry: Its entry (:func:`not_indexed_entry`).
    """
    store.put_revision(prepared.digest, prepared.text)
    store.put_not_indexed(entry)
