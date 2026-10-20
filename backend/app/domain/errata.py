"""
Erratum content: value types and the Markdown body parser.

An erratum is a separate Markdown file whose frontmatter names the
corrected decision in ``erratum-for`` (see ``docs/schema.md``). Its body
is split on ATX H2 headings into three sections:

- ``## Original text`` -- the text as written in the decision (optional,
  e.g. for pure additions);
- ``## Corrected text`` -- the replacement text (required);
- ``## Notes`` -- optional rationale.

Headings match case-insensitively and tolerate trailing whitespace or a
trailing colon. Headings inside fenced code blocks are content. Text
before the first heading and sections under any other H2 heading are
kept as notes and reported as ``erratum_unknown_section_heading``
warnings. A repeated section heading appends to that section.

The frontmatter part (:class:`ErratumHeader`) is validated by
:mod:`app.domain.validation`; :func:`build_erratum` joins it with the
parsed body into an :class:`ErratumContent`.

Public API: :class:`ErratumType`, :class:`ErratumHeader`,
:class:`ErratumContent`, :func:`parse_erratum_body`,
:func:`build_erratum`.
"""

import datetime
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.issues import Issue, IssueCode, error, warning

_H2_RE = re.compile(r"^ {0,3}##[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")

_ORIGINAL = "original"
_CORRECTED = "corrected"
_NOTES = "notes"

_SECTIONS = {
    "original text": _ORIGINAL,
    "corrected text": _CORRECTED,
    "notes": _NOTES,
}


class ErratumType(StrEnum):
    """Kind of correction an erratum reports."""

    TECHNICAL = "technical"
    EDITORIAL = "editorial"


@dataclass(frozen=True, slots=True)
class ErratumHeader:
    """
    Validated erratum frontmatter (everything except the target link).

    :param type: Erratum type, ``None`` if missing or invalid.
    :param section: Where in the decision the error is, if given.
    :param reported_by: Free-text reporter; informational only, never an
        identity.
    :param reported_date: Authored report ``date``, if valid.
    """

    type: ErratumType | None
    section: str | None = None
    reported_by: str | None = None
    reported_date: datetime.date | None = None


@dataclass(frozen=True, slots=True)
class ErratumContent:
    """
    The full content of one erratum, safe to persist.

    :param type: Erratum type, ``None`` if missing or invalid (reported
        as ``bad_erratum_type``).
    :param section: Where in the decision the error is, if given.
    :param reported_by: Free-text reporter; informational only.
    :param reported_date: Authored report date, if valid.
    :param original: Markdown of the "Original text" section, if any.
    :param corrected: Markdown of the "Corrected text" section; empty
        when missing (reported as ``erratum_missing_corrected_text``).
    :param notes: Markdown of the notes, including unrecognised content.
    """

    type: ErratumType | None
    section: str | None
    reported_by: str | None
    reported_date: datetime.date | None
    original: str | None
    corrected: str
    notes: str | None

    def to_dict(self) -> dict[str, str | None]:
        """
        Convert to a JSON-serialisable mapping.

        :returns: All fields by name; the type as its value and the date
            as ``YYYY-MM-DD``.
        """
        date = self.reported_date
        return {
            "type": None if self.type is None else self.type.value,
            "section": self.section,
            "reported_by": self.reported_by,
            "reported_date": None if date is None else date.isoformat(),
            "original": self.original,
            "corrected": self.corrected,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ErratumContent:
        """
        Rebuild content from :meth:`to_dict` output.

        :param data: Stored mapping; missing optional keys mean ``None``.
        :returns: The content.
        :raises ValueError: If the type or date is malformed, or a text
            value is not a string.
        """
        kind = _optional_text(data, "type")
        date = _optional_text(data, "reported_date")
        return cls(
            type=None if kind is None else ErratumType(kind),
            section=_optional_text(data, "section"),
            reported_by=_optional_text(data, "reported_by"),
            reported_date=(
                None if date is None else datetime.date.fromisoformat(date)
            ),
            original=_optional_text(data, "original"),
            corrected=_optional_text(data, "corrected") or "",
            notes=_optional_text(data, "notes"),
        )


def _optional_text(data: Mapping[str, object], name: str) -> str | None:
    """
    Read an optional string value from a stored mapping.

    :param data: Stored mapping.
    :param name: Key to read.
    :returns: The string, or ``None`` if absent.
    :raises ValueError: If the value is neither a string nor ``None``.
    """
    value = data.get(name)
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"erratum field {name!r} must be a string")


@dataclass(slots=True)
class _Block:
    """
    One run of body lines under a heading (or before the first one).

    :param heading: Heading text, ``None`` for the leading block.
    :param section: Recognised section name, ``None`` if unrecognised.
    :param lines: Content lines without the heading line.
    """

    heading: str | None
    section: str | None
    lines: list[str] = field(default_factory=list)


def _section_name(heading: str) -> str | None:
    """
    Map a heading text to a recognised section name.

    :param heading: H2 heading text.
    :returns: The section name, or ``None`` if not recognised.
    """
    key = " ".join(heading.rstrip().rstrip(":").split()).casefold()
    return _SECTIONS.get(key)


def _next_fence(line: str, fence: str | None) -> str | None:
    """
    Track whether a fenced code block is open after *line*.

    :param line: The current line.
    :param fence: The open fence marker, or ``None`` outside a fence.
    :returns: The open fence marker after the line, or ``None``.
    """
    match = _FENCE_RE.match(line)
    if fence is None:
        return match.group(1) if match else None
    closing = line.strip()
    if closing and set(closing) == {fence[0]} and len(closing) >= len(fence):
        return None
    return fence


def _split_blocks(body: str) -> list[_Block]:
    """
    Split a body into blocks at ATX H2 headings outside code fences.

    :param body: Markdown body.
    :returns: The leading block followed by one block per heading.
    """
    blocks = [_Block(None, None)]
    fence: str | None = None
    for line in body.split("\n"):
        in_fence = fence is not None
        fence = _next_fence(line, fence)
        match = None if in_fence else _H2_RE.match(line)
        if match is None:
            blocks[-1].lines.append(line)
            continue
        heading = match.group(1).strip()
        blocks.append(_Block(heading, _section_name(heading)))
    return blocks


def _trim(lines: list[str]) -> str:
    """
    Join lines, dropping leading and trailing blank lines.

    :param lines: Content lines.
    :returns: The text; empty if every line is blank.
    """
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def _unrecognised(block: _Block, text: str) -> tuple[str, Issue]:
    """
    Turn a leading or unrecognised block into notes text and a warning.

    :param block: The block.
    :param text: Its trimmed content (non-empty for the leading block).
    :returns: The text to keep as notes and the warning.
    """
    if block.heading is None:
        return text, warning(
            IssueCode.ERRATUM_UNKNOWN_SECTION_HEADING,
            "text before the first section heading is kept as notes; put "
            "it under `## Notes`",
        )
    kept = f"## {block.heading}\n\n{text}" if text else f"## {block.heading}"
    return kept, warning(
        IssueCode.ERRATUM_UNKNOWN_SECTION_HEADING,
        f"unknown section heading '{block.heading}' is kept as notes; "
        f"use 'Original text', 'Corrected text' or 'Notes'",
    )


def parse_erratum_body(
    body: str,
) -> tuple[str | None, str, str | None, tuple[Issue, ...]]:
    """
    Split an erratum body into its sections. Never raises.

    :param body: Markdown body without frontmatter.
    :returns: The original text (or ``None``), the corrected text
        (empty when missing), the notes (or ``None``) and the issues.
    """
    parts: dict[str, list[str]] = {_ORIGINAL: [], _CORRECTED: [], _NOTES: []}
    issues: list[Issue] = []
    for block in _split_blocks(body):
        text = _trim(block.lines)
        if block.section is not None:
            if text:
                parts[block.section].append(text)
        elif text or block.heading is not None:
            kept, issue = _unrecognised(block, text)
            parts[_NOTES].append(kept)
            issues.append(issue)
    joined = {name: "\n\n".join(texts) for name, texts in parts.items()}
    if not joined[_CORRECTED]:
        issues.append(
            error(
                IssueCode.ERRATUM_MISSING_CORRECTED_TEXT,
                "the erratum has no corrected text; add a `## Corrected "
                "text` heading followed by the corrected wording",
            )
        )
    return (
        joined[_ORIGINAL] or None,
        joined[_CORRECTED],
        joined[_NOTES] or None,
        tuple(issues),
    )


def build_erratum(
    header: ErratumHeader, body: str
) -> tuple[ErratumContent, tuple[Issue, ...]]:
    """
    Combine validated frontmatter with the parsed body.

    :param header: Validated erratum frontmatter.
    :param body: Markdown body without frontmatter.
    :returns: The erratum content and the body issues.
    """
    original, corrected, notes, issues = parse_erratum_body(body)
    content = ErratumContent(
        type=header.type,
        section=header.section,
        reported_by=header.reported_by,
        reported_date=header.reported_date,
        original=original,
        corrected=corrected,
        notes=notes,
    )
    return content, issues
