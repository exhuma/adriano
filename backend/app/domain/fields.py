"""
Validators for individual ADR frontmatter field values.

Each validator takes the raw value loaded from YAML plus the field name
and returns the normalised value together with any issues. Validators
never raise for bad content. They are used by
:func:`app.domain.records.parse_record`.

Public API: :data:`ISO_DATE_RE`, :data:`UUID_RE`, :func:`parse_uuid`,
:func:`parse_uuid_list`, :func:`parse_iso_date`, :func:`parse_date`,
:func:`parse_text`, :func:`parse_text_list`.
"""

import datetime
import re
import uuid

from app.domain.issues import Issue, IssueCode, error

#: Accepted spelling of dates: ``YYYY-MM-DD``.
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Accepted spelling of UUIDs: canonical hyphenated form, any case.
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_MAX_SHOWN = 60
_UUID_EXAMPLE = "0b0c2f4e-1a2b-4c3d-8e9f-001122334455"


def shown(value: object) -> str:
    """
    Render a value for an issue message, truncated to a sane length.

    :param value: Any loaded YAML value.
    :returns: A short quoted representation.
    """
    text = f"'{value}'" if isinstance(value, str) else repr(value)
    if len(text) > _MAX_SHOWN:
        return text[: _MAX_SHOWN - 3] + "..."
    return text


def _type_issue(field: str, expected: str, value: object) -> Issue:
    """
    Build a ``bad_field_type`` issue.

    :param field: Frontmatter field name.
    :param expected: Description of the expected type.
    :param value: The offending value.
    :returns: The issue.
    """
    return error(
        IssueCode.BAD_FIELD_TYPE,
        f"`{field}` must be {expected}; got {shown(value)}",
    )


def parse_uuid(
    value: object, field: str
) -> tuple[uuid.UUID | None, Issue | None]:
    """
    Validate a single UUID value.

    :param value: The loaded value.
    :param field: Field name used in the message.
    :returns: The UUID and ``None``, or ``None`` and a ``bad_uuid`` issue.
    """
    if isinstance(value, str) and UUID_RE.match(value.strip()):
        return uuid.UUID(value.strip()), None
    return None, error(
        IssueCode.BAD_UUID,
        f"`{field}` must be a UUID like {_UUID_EXAMPLE}; got {shown(value)}",
    )


def parse_uuid_list(
    value: object, field: str
) -> tuple[tuple[uuid.UUID, ...], list[Issue]]:
    """
    Validate a list of UUIDs (a single UUID string is also accepted).

    Invalid entries are dropped and reported; duplicates are removed
    while keeping the first occurrence.

    :param value: The loaded value.
    :param field: Field name used in messages.
    :returns: The valid UUIDs in order, and the issues found.
    """
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return (), [_type_issue(field, "a list of UUIDs", value)]
    found: list[uuid.UUID] = []
    issues: list[Issue] = []
    for item in value:
        parsed, issue = parse_uuid(item, field)
        if parsed is None:
            if issue is not None:
                issues.append(issue)
        elif parsed not in found:
            found.append(parsed)
    return tuple(found), issues


def parse_iso_date(text: str) -> datetime.date | None:
    """
    Parse a strict ``YYYY-MM-DD`` string.

    :param text: Candidate date text.
    :returns: The date, or ``None`` if the text is not a valid date.
    """
    if not ISO_DATE_RE.match(text):
        return None
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def parse_date(
    value: object, field: str
) -> tuple[datetime.date | None, Issue | None]:
    """
    Validate a date value written as ``YYYY-MM-DD``.

    :param value: The loaded value (a string; explicit YAML dates are
        accepted too).
    :param field: Field name used in the message.
    :returns: The date and ``None``, or ``None`` and a ``bad_date`` issue.
    """
    if isinstance(value, datetime.datetime):
        parsed = None
    elif isinstance(value, datetime.date):
        parsed = value
    elif isinstance(value, str):
        parsed = parse_iso_date(value.strip())
    else:
        parsed = None
    if parsed is not None:
        return parsed, None
    return None, error(
        IssueCode.BAD_DATE,
        f"`{field}` must be a valid date written YYYY-MM-DD; "
        f"got {shown(value)}",
    )


def parse_text(value: object, field: str) -> tuple[str | None, Issue | None]:
    """
    Validate a non-empty single-line text value.

    :param value: The loaded value.
    :param field: Field name used in the message.
    :returns: The stripped text and ``None``, or ``None`` and a
        ``bad_field_type`` issue.
    """
    if isinstance(value, str) and value.strip():
        return value.strip(), None
    return None, _type_issue(field, "a non-empty text", value)


def parse_text_list(
    value: object, field: str
) -> tuple[tuple[str, ...], list[Issue]]:
    """
    Validate a list of text entries (a single text is also accepted).

    Scalar entries such as numbers are converted to text; empty and
    nested entries are dropped and reported.

    :param value: The loaded value.
    :param field: Field name used in messages.
    :returns: The entries in order, and the issues found.
    """
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return (), [_type_issue(field, "a list of text entries", value)]
    found: list[str] = []
    issues: list[Issue] = []
    for item in value:
        if isinstance(item, str | int | float) and str(item).strip():
            found.append(str(item).strip())
        else:
            issues.append(_type_issue(field, "a list of text entries", item))
    return tuple(found), issues
