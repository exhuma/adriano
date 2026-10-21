"""Tests for ADR parsing and validation (``app.domain.records``)."""

import datetime
import json
import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.issues import Issue, IssueCode, Severity
from app.domain.records import (
    Links,
    RecordKind,
    TitleSource,
    is_adr_filename,
    parse_record,
    record_key,
)

UUID_A = "0b0c2f4e-1a2b-4c3d-8e9f-001122334455"
UUID_B = "11111111-2222-4333-8444-555555555555"
UUID_C = "99999999-2222-4333-8444-555555555555"
NAME = "doc/decisions/2024-12-24-use-postgresql.md"


def doc(frontmatter: str, body: str = "# Use PostgreSQL\n\nText.\n") -> bytes:
    """
    Build an ADR file from a frontmatter block and a body.

    :param frontmatter: YAML lines without delimiters.
    :param body: Markdown body.
    :returns: The encoded file.
    """
    return f"---\n{frontmatter}---\n{body}".encode()


def codes(issues: tuple[Issue, ...]) -> list[IssueCode]:
    """
    List the codes of some issues.

    :param issues: Issues to inspect.
    :returns: Their codes in order.
    """
    return [issue.code for issue in issues]


def issue_for(issues: tuple[Issue, ...], code: IssueCode) -> Issue:
    """
    Find the single issue with a code.

    :param issues: Issues to search.
    :param code: Code to look for.
    :returns: The matching issue.
    """
    (match,) = [issue for issue in issues if issue.code is code]
    return match


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("2024-12-24-use-postgresql.md", True),
        ("doc/decisions/sub/2024-01-02-x.md", True),
        ("2024-12-24-.md", True),
        ("use-postgresql.md", False),
        ("2024-12-24-use-postgresql.markdown", False),
        ("24-12-2024-use-postgresql.md", False),
        ("README.md", False),
    ],
)
def test_is_adr_filename(name: str, expected: bool) -> None:
    """Ensure only the legacy ``YYYY-MM-DD-*.md`` basenames match."""
    assert is_adr_filename(name) is expected


def test_complete_record_has_no_issues() -> None:
    """Ensure a fully valid modern record parses without issues."""
    raw = doc(
        f"uuid: {UUID_A}\ntitle: Use PostgreSQL\n"
        f"decision-date: 2024-12-24\nupdates: [{UUID_B}]\n"
    )

    record = parse_record(raw, filename=NAME)

    assert record.issues == ()
    assert record.adr_uuid == uuid.UUID(UUID_A)
    assert record.decision_date == datetime.date(2024, 12, 24)
    assert record.links == Links(updates=(uuid.UUID(UUID_B),))
    assert record.record_kind is RecordKind.DECISION
    assert record.approvable


def test_legacy_record_parses_with_expected_warnings() -> None:
    """Ensure a legacy file maps deprecates and signed-off-by with warnings."""
    raw = doc(
        f"uuid: {UUID_A}\ndecision-date: 2024-12-24\n"
        f"signed-off-by:\n  - alice@example.com\n  - bob@example.com\n"
        f"deprecates: {UUID_B}\n"
    )

    record = parse_record(raw, filename=NAME)

    assert codes(record.issues) == [
        IssueCode.LEGACY_ALIAS,
        IssueCode.LEGACY_SIGNOFF,
    ]
    assert all(i.severity is Severity.WARNING for i in record.issues)
    assert record.links.obsoletes == (uuid.UUID(UUID_B),)
    assert record.legacy_signoff == ("alice@example.com", "bob@example.com")
    assert record.approvable


def test_deprecates_merges_with_obsoletes_without_duplicates() -> None:
    """Ensure deprecates and obsoletes combine into one de-duplicated list."""
    raw = doc(
        f"uuid: {UUID_A}\ndecision-date: 2024-12-24\n"
        f"obsoletes: [{UUID_B}, {UUID_C}]\ndeprecates: {UUID_B}\n"
    )

    record = parse_record(raw, filename=NAME)

    assert record.links.obsoletes == (uuid.UUID(UUID_B), uuid.UUID(UUID_C))


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b"---\nuuid: [unclosed\n---\n", IssueCode.BAD_YAML),
        (b"---\n- just\n- a list\n---\n", IssueCode.BAD_YAML),
        (b"# No frontmatter\n", IssueCode.MISSING_FRONTMATTER),
        (b"---\nuuid: x\nno closing line\n", IssueCode.MISSING_FRONTMATTER),
        (doc("decision-date: 2024-12-24\n"), IssueCode.MISSING_UUID),
        (
            doc("uuid: not-a-uuid\ndecision-date: 2024-12-24\n"),
            IssueCode.BAD_UUID,
        ),
        (doc("uuid: 12345\ndecision-date: 2024-12-24\n"), IssueCode.BAD_UUID),
        (b"---\nuuid: \xff\n---\n", IssueCode.BAD_ENCODING),
    ],
    ids=[
        "bad-yaml",
        "not-a-mapping",
        "no-frontmatter",
        "unclosed",
        "missing-uuid",
        "bad-uuid",
        "numeric-uuid",
        "bad-encoding",
    ],
)
def test_identity_problems_are_errors_and_block_approval(
    raw: bytes, code: IssueCode
) -> None:
    """Ensure identity problems yield an error, no UUID, and no approval."""
    record = parse_record(raw, filename=NAME)

    issue = issue_for(record.issues, code)
    assert issue.severity is Severity.ERROR
    assert record.adr_uuid is None or code is IssueCode.BAD_ENCODING
    assert not record.approvable
    assert record.approval_blocker


def test_bad_yaml_message_names_the_line() -> None:
    """Ensure the YAML error message points at the file line."""
    raw = b"---\nuuid: a\ntitle: [unclosed\n---\n"

    record = parse_record(raw, filename=NAME)

    message = issue_for(record.issues, IssueCode.BAD_YAML).message
    assert "line" in message


@pytest.mark.parametrize(
    "value", ["24/12/2024", "2024-13-01", "2024-02-30", "'20241224'", "5"]
)
def test_bad_date_is_reported(value: str) -> None:
    """Ensure an invalid ``decision-date`` is reported, not substituted."""
    raw = doc(f"uuid: {UUID_A}\ndecision-date: {value}\n")

    record = parse_record(raw, filename=NAME)

    issue = issue_for(record.issues, IssueCode.BAD_DATE)
    assert "YYYY-MM-DD" in issue.message
    assert record.decision_date is None


def test_bad_date_message_quotes_value() -> None:
    """Ensure the bad-date message shows the offending value."""
    raw = doc(f"uuid: {UUID_A}\ndecision-date: 24/12/2024\n")

    record = parse_record(raw, filename=NAME)

    message = issue_for(record.issues, IssueCode.BAD_DATE).message
    assert message == (
        "`decision-date` must be a valid date written YYYY-MM-DD; "
        "got '24/12/2024'"
    )


def test_unknown_field_is_a_warning() -> None:
    """Ensure an unknown field yields a warning naming the field."""
    raw = doc(f"uuid: {UUID_A}\ndecision-date: 2024-12-24\nstatus: done\n")

    record = parse_record(raw, filename=NAME)

    issue = issue_for(record.issues, IssueCode.UNKNOWN_FIELD)
    assert issue.severity is Severity.WARNING
    assert "`status`" in issue.message
    assert record.approvable


def test_missing_date_uses_inferred_filename_date() -> None:
    """Ensure a missing date warns and exposes the filename date as inferred."""
    raw = doc(f"uuid: {UUID_A}\n")

    record = parse_record(raw, filename=NAME)

    assert codes(record.issues) == [IssueCode.MISSING_DATE]
    assert record.decision_date is None
    assert record.inferred_date == datetime.date(2024, 12, 24)
    assert record.decision_date_inferred
    assert record.display_date == datetime.date(2024, 12, 24)


def test_authored_date_is_not_inferred() -> None:
    """Ensure an authored date wins and is not flagged as inferred."""
    raw = doc(f"uuid: {UUID_A}\ndecision-date: 2023-01-05\n")

    record = parse_record(raw, filename=NAME)

    assert record.display_date == datetime.date(2023, 1, 5)
    assert not record.decision_date_inferred


@pytest.mark.parametrize(
    ("frontmatter", "body", "title", "source"),
    [
        (
            "title: Explicit\n",
            "# Heading\n",
            "Explicit",
            TitleSource.FRONTMATTER,
        ),
        ("", "Intro\n\n# Heading #\n", "Heading", TitleSource.H1),
        (
            "",
            "```\n# not a title\n```\n",
            "Use postgresql",
            TitleSource.FILENAME,
        ),
        ("", "## Only H2\n", "Use postgresql", TitleSource.FILENAME),
    ],
    ids=["frontmatter", "h1", "h1-in-fence", "filename"],
)
def test_title_fallbacks(
    frontmatter: str, body: str, title: str, source: TitleSource
) -> None:
    """Ensure the title falls back from frontmatter to H1 to filename."""
    raw = doc(f"uuid: {UUID_A}\n{frontmatter}", body)

    record = parse_record(raw, filename=NAME)

    assert (record.title, record.title_source) == (title, source)


LEGACY_SHAPES = [
    f"kind: erratum\ncorrects: {UUID_B}\n",
    "kind: erratum\n",
    "kind: ERRATUM\n",
    f"corrects: {UUID_B}\n",
]


@pytest.mark.parametrize(
    "legacy",
    LEGACY_SHAPES,
    ids=["kind-and-corrects", "kind-only", "kind-any-case", "corrects-only"],
)
def test_legacy_erratum_shape_is_rejected(legacy: str) -> None:
    """Ensure ``kind: erratum`` / ``corrects`` yield one legacy error."""
    raw = doc(f"uuid: {UUID_A}\ndecision-date: 2024-12-24\n{legacy}")

    record = parse_record(raw, filename=NAME)

    assert codes(record.issues) == [IssueCode.LEGACY_ERRATUM_FORMAT]
    issue = record.issues[0]
    assert issue.severity is Severity.ERROR
    assert "erratum-for" in issue.message
    assert "docs/developer/domain/schema.rst" in issue.message


def test_legacy_erratum_is_a_decision_without_link() -> None:
    """Ensure a legacy erratum is treated as a decision and not linked."""
    raw = doc(f"uuid: {UUID_A}\nkind: erratum\ncorrects: {UUID_B}\n")

    record = parse_record(raw, filename=NAME)

    assert record.record_kind is RecordKind.DECISION
    assert record.erratum is None
    assert record.links.corrects is None
    assert record.metadata["corrects"] == UUID_B


def test_kind_decision_is_a_warning_only() -> None:
    """Ensure ``kind: decision`` warns but stays a normal decision."""
    raw = doc(f"uuid: {UUID_A}\ndecision-date: 2024-12-24\nkind: decision\n")

    record = parse_record(raw, filename=NAME)

    assert codes(record.issues) == [IssueCode.OBSOLETE_KIND_FIELD]
    issue = record.issues[0]
    assert issue.severity is Severity.WARNING
    assert "kind" in issue.message
    assert "erratum-for" in issue.message
    assert record.record_kind is RecordKind.DECISION


@pytest.mark.parametrize("value", ["decision", "DECISION", "Decision"])
def test_kind_decision_any_case_is_a_warning(value: str) -> None:
    """Ensure ``kind: decision`` is matched case-insensitively."""
    raw = doc(f"uuid: {UUID_A}\ndecision-date: 2024-12-24\nkind: {value}\n")

    record = parse_record(raw, filename=NAME)

    assert codes(record.issues) == [IssueCode.OBSOLETE_KIND_FIELD]
    assert record.issues[0].severity is Severity.WARNING
    assert record.record_kind is RecordKind.DECISION


def test_kind_other_value_is_bad_field_type() -> None:
    """Ensure a ``kind`` value other than decision/erratum is rejected."""
    raw = doc(f"uuid: {UUID_A}\ndecision-date: 2024-12-24\nkind: memo\n")

    record = parse_record(raw, filename=NAME)

    assert codes(record.issues) == [IssueCode.BAD_FIELD_TYPE]
    issue = record.issues[0]
    assert issue.severity is Severity.ERROR
    assert "kind" in issue.message
    assert "obsolete" in issue.message
    assert record.record_kind is RecordKind.DECISION


def test_bad_link_entry_is_dropped() -> None:
    """Ensure invalid UUIDs in a link list are dropped and reported."""
    raw = doc(f"uuid: {UUID_A}\nupdates: [{UUID_B}, nope]\n")

    record = parse_record(raw, filename=NAME)

    assert IssueCode.BAD_UUID in codes(record.issues)
    assert record.links.updates == (uuid.UUID(UUID_B),)


def test_links_disabled_without_valid_uuid() -> None:
    """Ensure a record without a valid UUID has no outbound links."""
    raw = doc(f"uuid: nope\nobsoletes: [{UUID_B}]\n")

    record = parse_record(raw, filename=NAME)

    assert record.links == Links()
    assert record.metadata["obsoletes"] == [UUID_B]


def test_signoff_never_implies_approval() -> None:
    """Ensure legacy sign-off values are exposed only as unverified data."""
    raw = doc(f"uuid: {UUID_A}\nsigned-off-by: alice@example.com\n")

    record = parse_record(raw, filename=NAME)

    issue = issue_for(record.issues, IssueCode.LEGACY_SIGNOFF)
    assert "Legacy sign-off (unverified)" in issue.message
    assert record.legacy_signoff == ("alice@example.com",)


def test_crlf_and_bom_file_parses() -> None:
    """Ensure a Windows-style file with BOM parses like a canonical one."""
    raw = b"\xef\xbb\xbf" + doc(f"uuid: {UUID_A}\n").replace(b"\n", b"\r\n")

    record = parse_record(raw, filename=NAME)

    assert record.adr_uuid == uuid.UUID(UUID_A)
    assert record.body == "# Use PostgreSQL\n\nText.\n"


def test_bad_encoding_still_parses_content() -> None:
    """Ensure a non-UTF-8 file keeps its readable content for display."""
    raw = doc(f"uuid: {UUID_A}\n", "# Café\n").replace("é".encode(), b"\xe9")

    record = parse_record(raw, filename=NAME)

    assert record.adr_uuid == uuid.UUID(UUID_A)
    assert record.title == "Caf\ufffd"
    assert not record.encoding_ok
    assert not record.approvable


def test_result_is_json_serialisable() -> None:
    """Ensure metadata, links and issues serialise to JSON."""
    raw = doc(
        f"uuid: {UUID_A}\ndecision-date: !!timestamp 2024-12-24\n"
        f"extra: {{nested: [1, 2.5, true, null]}}\nupdates: [{UUID_B}]\n"
    )
    record = parse_record(raw, filename=NAME)

    payload = json.dumps(
        {
            "metadata": record.metadata,
            "links": record.links.to_dict(),
            "issues": record.issue_dicts(),
        }
    )

    assert UUID_B in payload
    assert Links.from_dict(record.links.to_dict()) == record.links
    assert [Issue.from_dict(d) for d in record.issue_dicts()] == list(
        record.issues
    )


def test_record_key_prefers_uuid() -> None:
    """Ensure the record key is the UUID string when available."""
    key = record_key(uuid.UUID(UUID_A), "central", "platform", NAME)

    assert key == UUID_A


def test_record_key_falls_back_to_source_location() -> None:
    """Ensure records without a UUID are keyed by source location."""
    key = record_key(None, "central", "platform", NAME)

    assert key == f"src:central/platform/{NAME}"


@given(st.binary(max_size=300))
def test_parse_record_never_raises(raw: bytes) -> None:
    """Ensure arbitrary bytes always parse into a record."""
    record = parse_record(b"---\n" + raw, filename=NAME)

    assert isinstance(record.title, str)


@given(st.text(max_size=200))
def test_parse_record_never_raises_on_text(body: str) -> None:
    """Ensure arbitrary frontmatter text always parses into a record."""
    record = parse_record(f"---\n{body}\n---\n".encode(), filename=NAME)

    assert record.title
