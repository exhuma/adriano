"""Tests for erratum link rules and body-parser robustness."""

import pytest

from app.domain.errata import parse_erratum_body
from app.domain.issues import IssueCode, Severity
from app.domain.records import RecordKind
from tests.domain.test_errata import (
    BODY,
    ERRATUM_UUID,
    TARGET_UUID,
    codes,
    only,
    parse,
)

OTHER_UUID = "9d2e0000-1a2b-4c3d-8e9f-001122334455"


def doc(target: str, extra: str = "") -> bytes:
    """
    Build an erratum file with a chosen ``erratum-for``.

    :param target: The ``erratum-for`` value.
    :param extra: Further frontmatter lines.
    :returns: The encoded file.
    """
    return (
        f"---\nuuid: {ERRATUM_UUID}\nerratum-for: {target}\n"
        f"type: technical\n{extra}---\n{BODY}"
    ).encode()


def test_erratum_targeting_itself_is_an_error_without_link() -> None:
    """Ensure `erratum-for` equal to the own uuid errors and is not linked."""
    record = parse(doc(ERRATUM_UUID))

    issue = only(record.issues, IssueCode.ERRATUM_TARGETS_ITSELF)
    assert issue.severity is Severity.ERROR
    assert "own `uuid`" in issue.message
    assert record.record_kind is RecordKind.ERRATUM
    assert record.links.corrects is None
    assert record.erratum is not None


@pytest.mark.parametrize(
    ("extra", "shown"),
    [
        (f"updates: [{OTHER_UUID}]\n", "`updates`"),
        (f"obsoletes: [{OTHER_UUID}]\n", "`obsoletes`"),
        (
            f"updates: [{OTHER_UUID}]\nobsoletes: [{OTHER_UUID}]\n",
            "`updates` and `obsoletes`",
        ),
    ],
)
def test_erratum_decision_relationships_are_dropped(
    extra: str, shown: str
) -> None:
    """Ensure updates/obsoletes on an erratum warn and are dropped."""
    record = parse(doc(TARGET_UUID, extra))

    issue = only(record.issues, IssueCode.ERRATUM_RELATIONSHIP_IGNORED)
    assert issue.severity is Severity.WARNING
    assert issue.message.startswith(shown + " on an erratum")
    assert record.links.updates == ()
    assert record.links.obsoletes == ()
    assert str(record.links.corrects) == TARGET_UUID


def test_self_target_with_updates_has_no_links() -> None:
    """Ensure the crash shape (self target plus updates) yields no links."""
    record = parse(doc(ERRATUM_UUID, f"updates: [{OTHER_UUID}]\n"))

    assert IssueCode.ERRATUM_TARGETS_ITSELF in codes(record.issues)
    assert IssueCode.ERRATUM_RELATIONSHIP_IGNORED in codes(record.issues)
    assert record.links.pairs() == ()


def test_decision_keeps_its_relationships() -> None:
    """Ensure decisions are unaffected by the erratum link rules."""
    raw = (
        f"---\nuuid: {ERRATUM_UUID}\ndecision-date: 2024-01-01\n"
        f"updates: [{OTHER_UUID}]\n---\nBody.\n"
    ).encode()

    record = parse(raw, filename="doc/decisions/2024-01-01-a.md")

    assert [str(t) for t in record.links.updates] == [OTHER_UUID]
    assert IssueCode.ERRATUM_RELATIONSHIP_IGNORED not in codes(record.issues)


@pytest.mark.parametrize("newline", ["\r\n", "\r"])
def test_body_line_endings_are_normalised(newline: str) -> None:
    """Ensure CRLF and CR bodies split like LF with no trailing CR."""
    body = BODY.replace("\n", newline)

    original, corrected, notes, issues = parse_erratum_body(body)

    assert (original, corrected, notes) == (
        "Use port 8080.",
        "Use port 8443.",
        "TLS is mandatory.",
    )
    assert issues == ()


def test_duplicate_section_heading_is_joined_with_warning() -> None:
    """Ensure a repeated heading concatenates and warns with its name."""
    body = (
        "## Corrected text\n\nFirst part.\n\n"
        "## Notes\n\nA note.\n\n"
        "## corrected text:\n\nSecond part.\n"
    )

    _original, corrected, notes, issues = parse_erratum_body(body)

    assert corrected == "First part.\n\nSecond part."
    assert notes == "A note."
    [issue] = issues
    assert issue.code is IssueCode.ERRATUM_DUPLICATE_SECTION
    assert issue.severity is Severity.WARNING
    assert "'corrected text:'" in issue.message


def test_each_repeat_is_reported() -> None:
    """Ensure every repeated heading occurrence gets its own warning."""
    body = "## Notes\n\na\n\n## Notes\n\nb\n\n## Notes\n\nc\n"

    _original, _corrected, notes, issues = parse_erratum_body(body)

    assert notes == "a\n\nb\n\nc"
    assert codes(issues) == [
        IssueCode.ERRATUM_DUPLICATE_SECTION,
        IssueCode.ERRATUM_DUPLICATE_SECTION,
        IssueCode.ERRATUM_MISSING_CORRECTED_TEXT,
    ]
