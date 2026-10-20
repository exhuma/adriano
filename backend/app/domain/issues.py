"""
Validation issue value types shared by the domain modules.

An issue is stored per record as ``{"severity", "code", "message"}``
(see :meth:`Issue.to_dict` / :meth:`Issue.from_dict`). Messages are short
and actionable and are meant to be shown to readers as-is.

Public API: :class:`Severity`, :class:`IssueCode`, :class:`Issue`,
:func:`has_errors`.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    """Severity of a validation issue."""

    ERROR = "error"
    WARNING = "warning"


class IssueCode(StrEnum):
    """Stable machine-readable validation issue codes."""

    BAD_YAML = "bad_yaml"
    MISSING_FRONTMATTER = "missing_frontmatter"
    MISSING_UUID = "missing_uuid"
    BAD_UUID = "bad_uuid"
    BAD_DATE = "bad_date"
    MISSING_DATE = "missing_date"
    UNKNOWN_FIELD = "unknown_field"
    BAD_FIELD_TYPE = "bad_field_type"
    DUPLICATE_UUID = "duplicate_uuid"
    MISSING_TARGET = "missing_target"
    AMBIGUOUS_TARGET = "ambiguous_target"
    LEGACY_ALIAS = "legacy_alias"
    LEGACY_SIGNOFF = "legacy_signoff"
    #: Retired: no longer emitted (``corrects`` is now a legacy field).
    #: Kept so issues stored by earlier versions still decode.
    CORRECTS_ON_NON_ERRATUM = "corrects_on_non_erratum"
    ERRATUM_WITHOUT_TARGET = "erratum_without_target"
    BAD_ENCODING = "bad_encoding"
    BAD_ERRATUM_TYPE = "bad_erratum_type"
    ERRATUM_MISSING_CORRECTED_TEXT = "erratum_missing_corrected_text"
    ERRATUM_UNKNOWN_SECTION_HEADING = "erratum_unknown_section_heading"
    LEGACY_ERRATUM_FORMAT = "legacy_erratum_format"


@dataclass(frozen=True, slots=True)
class Issue:
    """
    One validation finding for a record.

    :param severity: How serious the finding is.
    :param code: Stable issue code.
    :param message: Concise, actionable human-readable message.
    """

    severity: Severity
    code: IssueCode
    message: str

    def to_dict(self) -> dict[str, str]:
        """
        Convert the issue to a JSON-serialisable mapping.

        :returns: ``{"severity": ..., "code": ..., "message": ...}``.
        """
        return {
            "severity": self.severity.value,
            "code": self.code.value,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, str]) -> Issue:
        """
        Rebuild an issue from :meth:`to_dict` output.

        :param data: Mapping with ``severity``, ``code`` and ``message``.
        :returns: The issue.
        :raises ValueError: If severity or code is unknown.
        :raises KeyError: If a key is missing.
        """
        return cls(
            severity=Severity(data["severity"]),
            code=IssueCode(data["code"]),
            message=data["message"],
        )


def error(code: IssueCode, message: str) -> Issue:
    """
    Build an error-severity issue.

    :param code: Issue code.
    :param message: Human-readable message.
    :returns: The issue.
    """
    return Issue(Severity.ERROR, code, message)


def warning(code: IssueCode, message: str) -> Issue:
    """
    Build a warning-severity issue.

    :param code: Issue code.
    :param message: Human-readable message.
    :returns: The issue.
    """
    return Issue(Severity.WARNING, code, message)


def has_errors(issues: Iterable[Issue]) -> bool:
    """
    Tell whether any issue has error severity.

    :param issues: Issues to inspect.
    :returns: ``True`` if at least one issue is an error.
    """
    return any(issue.severity is Severity.ERROR for issue in issues)
