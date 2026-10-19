"""
Validation of a loaded frontmatter mapping against the record schema.

:func:`parse_fields` validates every known field, applies the legacy
mappings (``deprecates`` -> ``obsoletes``, ``signed-off-by`` -> legacy
sign-off) and collects issues in a stable order. It never raises.

Public API: :data:`KNOWN_FIELDS`, :class:`FieldValues`,
:func:`parse_fields`.
"""

import datetime
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from app.domain import fields as fv
from app.domain.issues import Issue, IssueCode, error, warning
from app.domain.values import Links, RecordKind

#: Frontmatter fields understood by the catalog.
KNOWN_FIELDS = frozenset(
    {
        "uuid",
        "title",
        "decision-date",
        "kind",
        "updates",
        "obsoletes",
        "corrects",
        "deprecates",
        "signed-off-by",
    }
)


@dataclass(frozen=True, slots=True)
class FieldValues:
    """
    Validated frontmatter values plus the issues found.

    :param adr_uuid: Record UUID, ``None`` if missing or invalid.
    :param title: Explicit title, if valid.
    :param decision_date: Authored decision date, if valid.
    :param record_kind: Record kind (default decision).
    :param links: Outbound links; empty when there is no valid UUID.
    :param legacy_signoff: Legacy ``signed-off-by`` entries.
    :param issues: Issues in a stable order.
    """

    adr_uuid: uuid.UUID | None
    title: str | None
    decision_date: datetime.date | None
    record_kind: RecordKind
    links: Links
    legacy_signoff: tuple[str, ...]
    issues: tuple[Issue, ...]

    @classmethod
    def empty(cls) -> FieldValues:
        """
        Build the values used when the frontmatter could not be read.

        :returns: Values with no UUID, no links and the default kind.
        """
        return cls(None, None, None, RecordKind.DECISION, Links(), (), ())


def _single[T](
    data: Mapping[str, object],
    name: str,
    parse: Callable[[object, str], tuple[T | None, Issue | None]],
    issues: list[Issue],
) -> T | None:
    """
    Validate one optional single-valued field.

    :param data: Frontmatter fields.
    :param name: Field name.
    :param parse: Validator from :mod:`app.domain.fields`.
    :param issues: Issue list to append to.
    :returns: The validated value, or ``None`` if absent or invalid.
    """
    if data.get(name) is None:
        return None
    value, issue = parse(data[name], name)
    if issue is not None:
        issues.append(issue)
    return value


def _uuid_list(
    data: Mapping[str, object], name: str, issues: list[Issue]
) -> tuple[uuid.UUID, ...]:
    """
    Validate one optional UUID-list field.

    :param data: Frontmatter fields.
    :param name: Field name.
    :param issues: Issue list to append to.
    :returns: Valid UUIDs, empty if absent.
    """
    if data.get(name) is None:
        return ()
    values, found = fv.parse_uuid_list(data[name], name)
    issues.extend(found)
    return values


def _uuid_field(
    data: Mapping[str, object], issues: list[Issue]
) -> uuid.UUID | None:
    """
    Validate the required ``uuid`` field.

    :param data: Frontmatter fields.
    :param issues: Issue list to append to.
    :returns: The UUID, or ``None`` if missing or invalid.
    """
    if data.get("uuid") is None:
        issues.append(
            error(
                IssueCode.MISSING_UUID,
                "`uuid` is missing; add a UUID so the record can be "
                "linked and approved",
            )
        )
        return None
    return _single(data, "uuid", fv.parse_uuid, issues)


def _date_field(
    data: Mapping[str, object],
    inferred: datetime.date | None,
    issues: list[Issue],
) -> datetime.date | None:
    """
    Validate ``decision-date`` and warn when it is absent.

    :param data: Frontmatter fields.
    :param inferred: Date from the filename, mentioned in the warning.
    :param issues: Issue list to append to.
    :returns: The authored date, or ``None``.
    """
    if data.get("decision-date") is not None:
        return _single(data, "decision-date", fv.parse_date, issues)
    hint = (
        f"; the filename date {inferred.isoformat()} is shown as inferred"
        if inferred is not None
        else ""
    )
    issues.append(
        warning(IssueCode.MISSING_DATE, f"`decision-date` is missing{hint}")
    )
    return None


def _kind_field(data: Mapping[str, object], issues: list[Issue]) -> RecordKind:
    """
    Validate ``kind``, defaulting to a decision.

    :param data: Frontmatter fields.
    :param issues: Issue list to append to.
    :returns: The record kind.
    """
    value = data.get("kind")
    if value is None:
        return RecordKind.DECISION
    if isinstance(value, str) and value.strip() in RecordKind:
        return RecordKind(value.strip())
    issues.append(
        error(
            IssueCode.BAD_FIELD_TYPE,
            f"`kind` must be one of decision, erratum; got {fv.shown(value)}",
        )
    )
    return RecordKind.DECISION


def _obsoletes(
    data: Mapping[str, object], issues: list[Issue]
) -> tuple[uuid.UUID, ...]:
    """
    Merge ``obsoletes`` with the legacy ``deprecates`` alias.

    :param data: Frontmatter fields.
    :param issues: Issue list to append to.
    :returns: The combined, de-duplicated targets.
    """
    obsoletes = _uuid_list(data, "obsoletes", issues)
    if "deprecates" not in data:
        return obsoletes
    issues.append(
        warning(
            IssueCode.LEGACY_ALIAS,
            "`deprecates` is a legacy alias; use `obsoletes` instead",
        )
    )
    legacy = _uuid_list(data, "deprecates", issues)
    return obsoletes + tuple(t for t in legacy if t not in obsoletes)


def _corrects(
    data: Mapping[str, object], kind: RecordKind, issues: list[Issue]
) -> uuid.UUID | None:
    """
    Validate ``corrects`` against the record kind.

    :param data: Frontmatter fields.
    :param kind: The validated record kind.
    :param issues: Issue list to append to.
    :returns: The corrected decision UUID, or ``None``.
    """
    corrects = _single(data, "corrects", fv.parse_uuid, issues)
    if kind is RecordKind.ERRATUM and corrects is None:
        issues.append(
            error(
                IssueCode.ERRATUM_WITHOUT_TARGET,
                "erratum records must name the corrected decision's UUID "
                "in `corrects`",
            )
        )
    if kind is not RecordKind.ERRATUM and data.get("corrects") is not None:
        issues.append(
            error(
                IssueCode.CORRECTS_ON_NON_ERRATUM,
                "`corrects` is only allowed with `kind: erratum`; the link "
                "is ignored",
            )
        )
        return None
    return corrects


def _signoff(
    data: Mapping[str, object], issues: list[Issue]
) -> tuple[str, ...]:
    """
    Read the legacy ``signed-off-by`` field.

    :param data: Frontmatter fields.
    :param issues: Issue list to append to.
    :returns: The unverified sign-off entries.
    """
    if "signed-off-by" not in data:
        return ()
    issues.append(
        warning(
            IssueCode.LEGACY_SIGNOFF,
            '`signed-off-by` is legacy and shown as "Legacy sign-off '
            '(unverified)"; it is not an approval',
        )
    )
    if data["signed-off-by"] is None:
        return ()
    values, found = fv.parse_text_list(data["signed-off-by"], "signed-off-by")
    issues.extend(found)
    return values


def _unknown_fields(data: Mapping[str, object]) -> list[Issue]:
    """
    Report fields the catalog does not understand.

    :param data: Frontmatter fields.
    :returns: One warning per unknown field.
    """
    return [
        warning(
            IssueCode.UNKNOWN_FIELD,
            f"unknown field `{name}` is ignored",
        )
        for name in data
        if name not in KNOWN_FIELDS
    ]


def parse_fields(
    data: Mapping[str, object], inferred: datetime.date | None
) -> FieldValues:
    """
    Validate all known frontmatter fields.

    :param data: Frontmatter fields.
    :param inferred: Date from the filename.
    :returns: The validated values and issues.
    """
    issues: list[Issue] = []
    adr_uuid = _uuid_field(data, issues)
    title = _single(data, "title", fv.parse_text, issues)
    decision_date = _date_field(data, inferred, issues)
    kind = _kind_field(data, issues)
    links = Links(
        updates=_uuid_list(data, "updates", issues),
        obsoletes=_obsoletes(data, issues),
        corrects=_corrects(data, kind, issues),
    )
    signoff = _signoff(data, issues)
    issues.extend(_unknown_fields(data))
    return FieldValues(
        adr_uuid=adr_uuid,
        title=title,
        decision_date=decision_date,
        record_kind=kind,
        links=links if adr_uuid is not None else Links(),
        legacy_signoff=signoff,
        issues=tuple(issues),
    )
