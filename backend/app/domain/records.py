"""
ADR record parsing, validation, title/date derivation and identity.

:func:`parse_record` turns the raw bytes of one Markdown ADR file into a
:class:`ParsedRecord`. It never raises for content problems: every
problem becomes an :class:`~app.domain.issues.Issue` and the record stays
storable and browseable.

Field handling (see ``docs/schema.md``):

- ``uuid`` -- required; canonical hyphenated UUID. Without a valid UUID
  the record is keyed by its source location (:func:`record_key`), its
  outbound relationships are disabled and it cannot be approved.
- ``title`` -- optional; fallback to the first Markdown H1, then to the
  humanised filename slug (:attr:`ParsedRecord.title_source`).
- ``decision-date`` -- optional ``YYYY-MM-DD``. The filename date is
  never substituted silently: it is exposed as
  :attr:`ParsedRecord.inferred_date` and flagged by
  :attr:`ParsedRecord.decision_date_inferred`.
- ``erratum-for`` -- makes the document an erratum of the decision with
  that UUID (stored as the internal ``corrects`` link). Errata also use
  ``type`` (required), ``section``, ``reported-by`` and ``date`` (the
  report date, exposed like ``decision-date``), and their body is
  parsed into :attr:`ParsedRecord.erratum` (:mod:`app.domain.errata`).
  Without an explicit ``title`` an erratum is titled "Erratum:
  <section>", else "Erratum: <humanised filename slug>".
- ``kind`` / ``corrects`` -- the retired erratum shape; rejected with
  ``legacy_erratum_format`` and the file is treated as a decision.
- ``updates`` / ``obsoletes`` -- lists of UUIDs.
- ``deprecates`` -- legacy alias merged into ``obsoletes`` (warning).
- ``signed-off-by`` -- legacy, exposed as
  :attr:`ParsedRecord.legacy_signoff` for display as "Legacy sign-off
  (unverified)"; it never implies approval.

The value types and helpers live in :mod:`app.domain.values`,
:mod:`app.domain.titles` and :mod:`app.domain.validation`; this module
re-exports them so callers need a single import.

Public API:

- :data:`ADR_FILENAME_RE`, :data:`KNOWN_FIELDS`
- :class:`RecordKind`, :class:`TitleSource`, :class:`LinkType`,
  :class:`Links`, :class:`Identity`, :class:`ParsedRecord`
- :class:`ErratumContent`, :class:`ErratumType`
- :func:`is_adr_filename`, :func:`filename_date`, :func:`derive_title`,
  :func:`record_key`, :func:`parse_record`
"""

import datetime
import uuid
from dataclasses import dataclass

from app.domain.errata import ErratumContent, ErratumType, build_erratum
from app.domain.frontmatter import (
    JsonValue,
    json_safe,
    load_frontmatter,
    split_frontmatter,
)
from app.domain.hashing import canonicalize, canonicalize_text
from app.domain.issues import Issue, IssueCode, error, has_errors
from app.domain.titles import (
    ADR_FILENAME_RE,
    derive_title,
    erratum_title,
    filename_date,
    is_adr_filename,
)
from app.domain.validation import KNOWN_FIELDS, FieldValues, parse_fields
from app.domain.values import (
    Identity,
    Links,
    LinkType,
    RecordKind,
    TitleSource,
    record_key,
)

__all__ = [
    "ADR_FILENAME_RE",
    "KNOWN_FIELDS",
    "ErratumContent",
    "ErratumType",
    "Identity",
    "LinkType",
    "Links",
    "ParsedRecord",
    "RecordKind",
    "TitleSource",
    "derive_title",
    "filename_date",
    "is_adr_filename",
    "parse_record",
    "record_key",
]


@dataclass(frozen=True, slots=True)
class ParsedRecord:
    """
    Result of parsing one ADR file. All fields are safe to persist.

    :param body: Markdown body without the frontmatter block.
    :param metadata: Raw frontmatter as JSON-serialisable values.
    :param title: Display title.
    :param title_source: Where :attr:`title` came from.
    :param decision_date: Authored ``decision-date`` (``date`` for an
        erratum), if valid.
    :param inferred_date: Date taken from the filename, if any.
    :param links: Validated outbound links (empty without a valid UUID).
    :param adr_uuid: Authored record UUID, or ``None`` if missing/invalid.
    :param legacy_signoff: Unverified legacy ``signed-off-by`` values.
    :param issues: Validation issues in a stable order.
    :param encoding_ok: ``False`` if the bytes were not valid UTF-8.
    :param erratum: Erratum content, ``None`` for a decision.
    """

    body: str
    metadata: dict[str, JsonValue]
    title: str
    title_source: TitleSource
    decision_date: datetime.date | None
    inferred_date: datetime.date | None
    links: Links
    adr_uuid: uuid.UUID | None
    legacy_signoff: tuple[str, ...]
    issues: tuple[Issue, ...]
    encoding_ok: bool = True
    erratum: ErratumContent | None = None

    @property
    def record_kind(self) -> RecordKind:
        """
        Tell whether this is a decision or an erratum.

        :returns: :attr:`RecordKind.ERRATUM` iff :attr:`erratum` is set.
        """
        if self.erratum is None:
            return RecordKind.DECISION
        return RecordKind.ERRATUM

    @property
    def decision_date_inferred(self) -> bool:
        """
        Tell whether the shown date is only inferred from the filename.

        :returns: ``True`` when no ``decision-date`` was authored but the
            filename carries a date.
        """
        return self.decision_date is None and self.inferred_date is not None

    @property
    def display_date(self) -> datetime.date | None:
        """
        Date to display.

        Label it "inferred from filename" when
        :attr:`decision_date_inferred` is true.

        :returns: The authored date, else the filename date, else ``None``.
        """
        return self.decision_date or self.inferred_date

    @property
    def has_errors(self) -> bool:
        """
        Tell whether any issue has error severity.

        :returns: ``True`` if at least one error was found.
        """
        return has_errors(self.issues)

    @property
    def approval_blocker(self) -> str | None:
        """
        Explain why this content cannot be approved, if it cannot.

        :returns: A reader-facing reason, or ``None`` if approvable.
        """
        if not self.encoding_ok:
            return "the file is not valid UTF-8"
        if self.adr_uuid is None:
            return "the record has no valid `uuid`"
        return None

    @property
    def approvable(self) -> bool:
        """
        Tell whether a reviewer may accept or reject this content.

        :returns: ``True`` if there is no identity or encoding error.
        """
        return self.approval_blocker is None

    def issue_dicts(self) -> list[dict[str, str]]:
        """
        Convert :attr:`issues` to the stored JSON shape.

        :returns: One mapping per issue.
        """
        return [issue.to_dict() for issue in self.issues]


def _decode(raw: bytes) -> tuple[str, Issue | None]:
    """
    Decode and canonicalize bytes, replacing invalid UTF-8 if needed.

    :param raw: The exact file bytes.
    :returns: Canonical text and a ``bad_encoding`` issue if the bytes
        were not valid UTF-8.
    """
    try:
        return canonicalize(raw), None
    except UnicodeDecodeError as exc:
        text = canonicalize_text(raw.decode("utf-8", errors="replace"))
        return text, error(
            IssueCode.BAD_ENCODING,
            f"file is not valid UTF-8 (first bad byte at offset "
            f"{exc.start}); save it as UTF-8. It cannot be approved "
            f"until fixed",
        )


def _frontmatter_fields(
    text: str,
) -> tuple[dict[str, object], str, Issue | None]:
    """
    Split and load the frontmatter of canonical text.

    :param text: Canonical document text.
    :returns: The loaded fields, the body, and a structural issue
        (``missing_frontmatter`` or ``bad_yaml``) if any.
    """
    split = split_frontmatter(text)
    if split.unclosed:
        return (
            {},
            split.body,
            error(
                IssueCode.MISSING_FRONTMATTER,
                "frontmatter is not closed; add a `---` line after the fields",
            ),
        )
    if split.yaml_text is None:
        return (
            {},
            split.body,
            error(
                IssueCode.MISSING_FRONTMATTER,
                "no frontmatter; start the file with `---`, the fields (at "
                "least `uuid`), and a closing `---` line",
            ),
        )
    loaded = load_frontmatter(split.yaml_text)
    return loaded.fields, split.body, loaded.issue


def _erratum(
    parsed: FieldValues, body: str, issues: list[Issue]
) -> ErratumContent | None:
    """
    Parse the erratum body when the frontmatter declares an erratum.

    :param parsed: Validated frontmatter.
    :param body: Markdown body.
    :param issues: Issue list to append the body issues to.
    :returns: The erratum content, or ``None`` for a decision.
    """
    if parsed.erratum is None:
        return None
    content, found = build_erratum(parsed.erratum, body)
    issues.extend(found)
    return content


def _title(
    parsed: FieldValues, body: str, filename: str
) -> tuple[str, TitleSource]:
    """
    Choose the display title for a decision or an erratum.

    :param parsed: Validated frontmatter.
    :param body: Markdown body.
    :param filename: File name or repository path.
    :returns: The title and where it came from.
    """
    if parsed.erratum is not None and parsed.title is None:
        return erratum_title(parsed.erratum.section, filename)
    return derive_title(parsed.title, body, filename)


def parse_record(raw: bytes, *, filename: str) -> ParsedRecord:
    """
    Parse and validate one ADR file. Never raises for content problems.

    :param raw: The exact bytes fetched or pushed.
    :param filename: File name or repository path (used for the title
        fallback and the inferred date only).
    :returns: The parsed record with all issues found.
    """
    text, encoding_issue = _decode(raw)
    data, body, structure_issue = _frontmatter_fields(text)
    inferred = filename_date(filename)
    issues = [i for i in (encoding_issue, structure_issue) if i is not None]
    if structure_issue is None:
        parsed = parse_fields(data, inferred)
        issues.extend(parsed.issues)
    else:
        parsed = FieldValues.empty()
    erratum = _erratum(parsed, body, issues)
    title, title_source = _title(parsed, body, filename)
    return ParsedRecord(
        body=body,
        metadata={name: json_safe(value) for name, value in data.items()},
        title=title,
        title_source=title_source,
        decision_date=parsed.decision_date,
        inferred_date=inferred,
        links=parsed.links,
        adr_uuid=parsed.adr_uuid,
        legacy_signoff=parsed.legacy_signoff,
        issues=tuple(issues),
        encoding_ok=encoding_issue is None,
        erratum=erratum,
    )
