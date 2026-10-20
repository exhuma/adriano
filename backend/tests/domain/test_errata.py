"""Tests for the erratum format (``app.domain.errata`` and parsing)."""

import datetime
import json
import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.errata import ErratumContent, ErratumType, parse_erratum_body
from app.domain.issues import Issue, IssueCode, Severity
from app.domain.records import (
    Identity,
    LinkType,
    ParsedRecord,
    RecordKind,
    TitleSource,
    parse_record,
)
from app.domain.relationships import RecordSummary, resolve_relationships

ERRATUM_UUID = "7c1e0000-1a2b-4c3d-8e9f-001122334455"
TARGET_UUID = "0b0c2f4e-1a2b-4c3d-8e9f-001122334455"
NAME = "doc/decisions/errata/2025-05-01-fix-port-number.md"
BODY = (
    "## Original text\n\nUse port 8080.\n\n"
    "## Corrected text\n\nUse port 8443.\n\n"
    "## Notes\n\nTLS is mandatory.\n"
)


def erratum_doc(extra: str = "type: technical\n", body: str = BODY) -> bytes:
    """
    Build an erratum file with a valid ``uuid`` and ``erratum-for``.

    :param extra: Further frontmatter lines.
    :param body: Markdown body.
    :returns: The encoded file.
    """
    return (
        f"---\nuuid: {ERRATUM_UUID}\nerratum-for: {TARGET_UUID}\n"
        f"{extra}---\n{body}"
    ).encode()


def codes(issues: tuple[Issue, ...]) -> list[IssueCode]:
    """
    List the codes of some issues.

    :param issues: Issues to inspect.
    :returns: Their codes in order.
    """
    return [issue.code for issue in issues]


def only(issues: tuple[Issue, ...], code: IssueCode) -> Issue:
    """
    Find the single issue with a code.

    :param issues: Issues to search.
    :param code: Code to look for.
    :returns: The matching issue.
    """
    (match,) = [issue for issue in issues if issue.code is code]
    return match


def parse(raw: bytes, filename: str = NAME) -> ParsedRecord:
    """
    Parse a file with the default erratum file name.

    :param raw: File bytes.
    :param filename: File name.
    :returns: The parsed record.
    """
    return parse_record(raw, filename=filename)


# -- body parser ----------------------------------------------------------


def test_body_with_all_sections() -> None:
    """Ensure all three sections are extracted without issues."""
    original, corrected, notes, issues = parse_erratum_body(BODY)

    assert original == "Use port 8080."
    assert corrected == "Use port 8443."
    assert notes == "TLS is mandatory."
    assert issues == ()


def test_body_sections_in_any_order() -> None:
    """Ensure section order does not matter."""
    body = "## Notes\nWhy.\n## Corrected text\nNew.\n## Original text\nOld.\n"

    assert parse_erratum_body(body) == ("Old.", "New.", "Why.", ())


def test_only_corrected_text_is_required() -> None:
    """Ensure original and notes are optional."""
    original, corrected, notes, issues = parse_erratum_body(
        "## Corrected text\n\nAdd a retry.\n"
    )

    assert (original, corrected, notes, issues) == (
        None,
        "Add a retry.",
        None,
        (),
    )


@pytest.mark.parametrize(
    "heading",
    [
        "## corrected TEXT",
        "## Corrected text:",
        "## Corrected text  ",
        "## Corrected text ##",
        "   ##   Corrected   text :",
    ],
)
def test_heading_matching_is_tolerant(heading: str) -> None:
    """Ensure case, spacing and a trailing colon do not matter."""
    _, corrected, _, issues = parse_erratum_body(f"{heading}\nFixed.\n")

    assert corrected == "Fixed."
    assert issues == ()


def test_heading_inside_code_fence_is_content() -> None:
    """Ensure a heading inside a fenced code block is not a section."""
    body = (
        "## Original text\n"
        "```markdown\n## Corrected text\nnot a heading\n```\n"
        "## Corrected text\n~~~~\n## Notes\n~~~\nstill code\n~~~~\n"
    )

    original, corrected, notes, issues = parse_erratum_body(body)

    assert original == "```markdown\n## Corrected text\nnot a heading\n```"
    assert corrected == "~~~~\n## Notes\n~~~\nstill code\n~~~~"
    assert notes is None
    assert issues == ()


def test_unknown_heading_is_kept_as_notes_with_warning() -> None:
    """Ensure an unrecognised H2 section moves to notes with a warning."""
    body = "## Corrected text\nNew.\n## Example\nSee here.\n## Notes\nWhy.\n"

    _, corrected, notes, issues = parse_erratum_body(body)

    assert corrected == "New."
    assert notes == "## Example\n\nSee here.\n\nWhy."
    issue = only(issues, IssueCode.ERRATUM_UNKNOWN_SECTION_HEADING)
    assert issue.severity is Severity.WARNING
    assert "'Example'" in issue.message


def test_leading_text_is_kept_as_notes_with_warning() -> None:
    """Ensure text before the first heading moves to notes with a warning."""
    body = "Reported on chat.\n\n## Corrected text\nNew.\n"

    _, _, notes, issues = parse_erratum_body(body)

    assert notes == "Reported on chat."
    assert codes(issues) == [IssueCode.ERRATUM_UNKNOWN_SECTION_HEADING]


def test_deeper_headings_stay_in_their_section() -> None:
    """Ensure H3 headings are content of the enclosing section."""
    body = "## Corrected text\n### Detail\nNew.\n"

    _, corrected, _, issues = parse_erratum_body(body)

    assert corrected == "### Detail\nNew."
    assert issues == ()


@pytest.mark.parametrize(
    "body",
    ["", "## Original text\nOld.\n", "## Corrected text\n\n   \n## Notes\n"],
    ids=["empty", "no-heading", "blank-section"],
)
def test_missing_corrected_text_is_an_error(body: str) -> None:
    """Ensure a missing or empty corrected text is an error."""
    _, corrected, _, issues = parse_erratum_body(body)

    assert corrected == ""
    issue = only(issues, IssueCode.ERRATUM_MISSING_CORRECTED_TEXT)
    assert issue.severity is Severity.ERROR
    assert "## Corrected text" in issue.message


@given(st.text(max_size=300))
def test_body_parser_never_raises(body: str) -> None:
    """Ensure arbitrary bodies always parse."""
    _, corrected, _, _ = parse_erratum_body(body)

    assert isinstance(corrected, str)


# -- frontmatter ----------------------------------------------------------


@pytest.mark.parametrize("kind", list(ErratumType))
def test_valid_erratum_parses_without_issues(kind: ErratumType) -> None:
    """Ensure a complete technical or editorial erratum has no issues."""
    raw = erratum_doc(
        f"type: {kind.value}\nsection: Consequences\n"
        "reported-by: alice@example.com\ndate: 2025-05-02\n"
    )

    record = parse(raw)

    assert record.issues == ()
    assert record.record_kind is RecordKind.ERRATUM
    assert record.links.corrects == uuid.UUID(TARGET_UUID)
    assert record.erratum == ErratumContent(
        type=kind,
        section="Consequences",
        reported_by="alice@example.com",
        reported_date=datetime.date(2025, 5, 2),
        original="Use port 8080.",
        corrected="Use port 8443.",
        notes="TLS is mandatory.",
    )
    assert record.approvable


def test_missing_type_is_an_error() -> None:
    """Ensure an erratum without ``type`` is reported."""
    record = parse(erratum_doc(""))

    issue = only(record.issues, IssueCode.BAD_ERRATUM_TYPE)
    assert issue.severity is Severity.ERROR
    assert "`type` is required" in issue.message
    assert record.erratum is not None
    assert record.erratum.type is None


def test_bad_type_is_an_error() -> None:
    """Ensure an unknown ``type`` value is reported with the choices."""
    record = parse(erratum_doc("type: cosmetic\n"))

    issue = only(record.issues, IssueCode.BAD_ERRATUM_TYPE)
    assert "technical, editorial" in issue.message
    assert "'cosmetic'" in issue.message
    assert record.erratum is not None
    assert record.erratum.type is None


def test_type_is_case_insensitive() -> None:
    """Ensure ``type`` accepts any letter case."""
    record = parse(erratum_doc("type: Editorial\n"))

    assert record.erratum is not None
    assert record.erratum.type is ErratumType.EDITORIAL


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("", [IssueCode.ERRATUM_WITHOUT_TARGET]),
        ("nope", [IssueCode.BAD_UUID, IssueCode.ERRATUM_WITHOUT_TARGET]),
    ],
    ids=["empty", "bad-uuid"],
)
def test_missing_or_bad_target_is_an_error(
    target: str, expected: list[IssueCode]
) -> None:
    """Ensure an erratum without a valid ``erratum-for`` is not linked."""
    raw = (
        f"---\nuuid: {ERRATUM_UUID}\nerratum-for: {target}\n"
        f"type: technical\n---\n{BODY}"
    ).encode()

    record = parse(raw)

    assert codes(record.issues) == expected
    assert record.record_kind is RecordKind.ERRATUM
    assert record.links.corrects is None
    message = only(record.issues, IssueCode.ERRATUM_WITHOUT_TARGET).message
    assert "`erratum-for`" in message


def test_erratum_without_uuid_is_not_approvable() -> None:
    """Ensure an erratum still needs its own ``uuid``."""
    raw = f"---\nerratum-for: {TARGET_UUID}\ntype: technical\n---\n{BODY}"

    record = parse(raw.encode())

    assert IssueCode.MISSING_UUID in codes(record.issues)
    assert not record.approvable
    assert record.links.corrects is None


def test_report_date_is_the_display_date() -> None:
    """Ensure ``date`` is used as the authored date, not inferred."""
    record = parse(erratum_doc("type: technical\ndate: 2025-06-01\n"))

    assert record.decision_date == datetime.date(2025, 6, 1)
    assert not record.decision_date_inferred


def test_missing_report_date_is_inferred_without_warning() -> None:
    """Ensure a missing ``date`` falls back to the filename date silently."""
    record = parse(erratum_doc())

    assert record.issues == ()
    assert record.decision_date is None
    assert record.decision_date_inferred
    assert record.display_date == datetime.date(2025, 5, 1)


def test_bad_report_date_is_reported() -> None:
    """Ensure an invalid ``date`` yields ``bad_date``."""
    record = parse(erratum_doc("type: technical\ndate: 01/05/2025\n"))

    issue = only(record.issues, IssueCode.BAD_DATE)
    assert "`date`" in issue.message
    assert record.decision_date is None


def test_decision_date_on_erratum_is_unknown() -> None:
    """Ensure ``decision-date`` on an erratum points to ``date``."""
    record = parse(erratum_doc("type: technical\ndecision-date: 2025-01-01\n"))

    issue = only(record.issues, IssueCode.UNKNOWN_FIELD)
    assert "`date`" in issue.message
    assert record.decision_date is None


@pytest.mark.parametrize(
    "line",
    [
        "type: technical",
        "section: Context",
        "reported-by: bob",
        "date: 2025-01-01",
    ],
)
def test_erratum_fields_on_decision_are_unknown(line: str) -> None:
    """Ensure erratum-only fields on a decision only warn."""
    raw = (
        f"---\nuuid: {TARGET_UUID}\ndecision-date: 2024-01-01\n{line}\n---\n"
        "# Title\n"
    ).encode()

    record = parse(raw, "doc/decisions/2024-01-01-x.md")

    issue = only(record.issues, IssueCode.UNKNOWN_FIELD)
    assert issue.severity is Severity.WARNING
    assert "erratum-for" in issue.message
    assert record.record_kind is RecordKind.DECISION


def test_body_issues_follow_frontmatter_issues() -> None:
    """Ensure body problems are reported on the record."""
    record = parse(erratum_doc("", "Just prose.\n"))

    assert codes(record.issues) == [
        IssueCode.BAD_ERRATUM_TYPE,
        IssueCode.ERRATUM_UNKNOWN_SECTION_HEADING,
        IssueCode.ERRATUM_MISSING_CORRECTED_TEXT,
    ]


def test_decision_has_no_erratum() -> None:
    """Ensure a plain decision has no erratum content."""
    raw = f"---\nuuid: {TARGET_UUID}\ndecision-date: 2024-01-01\n---\n# T\n"

    record = parse(raw.encode(), "doc/decisions/2024-01-01-x.md")

    assert record.erratum is None
    assert record.record_kind is RecordKind.DECISION


# -- titles ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "body", "title", "source"),
    [
        (
            "title: Port fix\nsection: Context\n",
            BODY,
            "Port fix",
            TitleSource.FRONTMATTER,
        ),
        (
            "section: Consequences\n",
            BODY,
            "Erratum: Consequences",
            TitleSource.FRONTMATTER,
        ),
        ("", "# Ignored H1\n" + BODY, "Erratum: Fix port number", None),
    ],
    ids=["explicit", "section", "filename"],
)
def test_erratum_title_fallbacks(
    extra: str, body: str, title: str, source: TitleSource | None
) -> None:
    """Ensure an erratum is titled by title, then section, then filename."""
    record = parse(erratum_doc(f"type: technical\n{extra}", body))

    assert record.title == title
    assert record.title_source is (source or TitleSource.FILENAME)


# -- serialisation --------------------------------------------------------


def test_content_round_trips_through_json() -> None:
    """Ensure erratum content survives ``to_dict`` / JSON / ``from_dict``."""
    record = parse(erratum_doc("type: editorial\ndate: 2025-05-02\n"))
    assert record.erratum is not None

    data = json.loads(json.dumps(record.erratum.to_dict()))

    assert data["type"] == "editorial"
    assert data["reported_date"] == "2025-05-02"
    assert ErratumContent.from_dict(data) == record.erratum


def test_content_without_optional_values_round_trips() -> None:
    """Ensure ``None`` values (including type) round-trip."""
    content = ErratumContent(None, None, None, None, None, "", None)

    assert ErratumContent.from_dict(content.to_dict()) == content


@pytest.mark.parametrize(
    "data",
    [
        {"type": "cosmetic", "corrected": "x"},
        {"reported_date": "May 1", "corrected": "x"},
        {"section": 3, "corrected": "x"},
    ],
    ids=["bad-type", "bad-date", "bad-text"],
)
def test_from_dict_rejects_malformed_data(data: dict[str, object]) -> None:
    """Ensure malformed stored content raises ``ValueError``."""
    with pytest.raises(ValueError):
        ErratumContent.from_dict(data)


# -- relationships --------------------------------------------------------


def _summary(key: str, record: ParsedRecord) -> RecordSummary:
    """
    Build a relationship summary from a parsed record.

    :param key: Row key.
    :param record: The parsed record.
    :returns: The summary.
    """
    return RecordSummary(
        key=key,
        identity=Identity("central", "platform", str(record.adr_uuid)),
        adr_uuid=record.adr_uuid,
        links=record.links,
        record_kind=record.record_kind,
    )


def test_erratum_is_listed_on_its_target() -> None:
    """Ensure the target lists the erratum and the erratum links back."""
    target = parse(
        f"---\nuuid: {TARGET_UUID}\n---\n# Target\n".encode(),
        "doc/decisions/2024-01-01-target.md",
    )
    summaries = [
        _summary("target", target),
        _summary("fix", parse(erratum_doc())),
    ]

    view = resolve_relationships(summaries, "target")
    own = resolve_relationships(summaries, "fix")

    assert view.errata == ("fix",)
    assert view.inbound == ()
    [link] = own.outbound
    assert (link.link_type, link.target_key) == (LinkType.CORRECTS, "target")
