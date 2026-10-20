"""
Validation of a loaded frontmatter mapping against the record schema.

:func:`parse_fields` validates every known field, applies the legacy
mappings (``deprecates`` -> ``obsoletes``, ``signed-off-by`` -> legacy
sign-off) and collects issues in a stable order. It never raises.

A document is an erratum if and only if its frontmatter has
``erratum-for``. Errata use ``type``, ``section``, ``reported-by`` and
``date`` instead of ``decision-date``; those fields on a decision are
reported as unknown. The retired erratum shape (``kind: erratum`` with
``corrects:``) yields ``legacy_erratum_format`` and creates no link.

Public API: :data:`KNOWN_FIELDS`, :data:`DECISION_FIELDS`,
:data:`ERRATUM_FIELDS`, :data:`LEGACY_ERRATUM_FIELDS`,
:class:`FieldValues`, :func:`parse_fields`.
"""

import datetime
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from app.domain import fields as fv
from app.domain.errata import ErratumHeader
from app.domain.issues import Issue, IssueCode, error, warning
from app.domain.values import Links

_COMMON_FIELDS = frozenset(
    {"uuid", "title", "updates", "obsoletes", "deprecates", "signed-off-by"}
)

#: Frontmatter fields understood on a decision.
DECISION_FIELDS = _COMMON_FIELDS | {"decision-date"}

#: Frontmatter fields understood on an erratum.
ERRATUM_FIELDS = _COMMON_FIELDS | {
    "erratum-for",
    "type",
    "section",
    "reported-by",
    "date",
}

#: Frontmatter fields understood by the catalog.
KNOWN_FIELDS = DECISION_FIELDS | ERRATUM_FIELDS

#: Fields of the retired erratum shape (``legacy_erratum_format``).
LEGACY_ERRATUM_FIELDS = frozenset({"kind", "corrects"})

_LEGACY_ERRATUM_MESSAGE = (
    "`kind: erratum` / `corrects:` is no longer supported; errata use "
    "`erratum-for: <uuid>` with `type`, and body sections 'Original "
    "text' / 'Corrected text' / 'Notes' (see docs/schema.md)"
)


@dataclass(frozen=True, slots=True)
class FieldValues:
    """
    Validated frontmatter values plus the issues found.

    :param adr_uuid: Record UUID, ``None`` if missing or invalid.
    :param title: Explicit title, if valid.
    :param decision_date: Authored decision date (the report ``date``
        for an erratum), if valid.
    :param erratum: Erratum frontmatter, ``None`` for a decision.
    :param links: Outbound links; empty when there is no valid UUID.
    :param legacy_signoff: Legacy ``signed-off-by`` entries.
    :param issues: Issues in a stable order.
    """

    adr_uuid: uuid.UUID | None
    title: str | None
    decision_date: datetime.date | None
    erratum: ErratumHeader | None
    links: Links
    legacy_signoff: tuple[str, ...]
    issues: tuple[Issue, ...]

    @classmethod
    def empty(cls) -> FieldValues:
        """
        Build the values used when the frontmatter could not be read.

        :returns: Values for a decision with no UUID and no links.
        """
        return cls(None, None, None, None, Links(), (), ())


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


def _erratum_header(
    data: Mapping[str, object], issues: list[Issue]
) -> ErratumHeader:
    """
    Validate ``type``, ``section``, ``reported-by`` and ``date``.

    :param data: Frontmatter fields of an erratum.
    :param issues: Issue list to append to.
    :returns: The validated erratum frontmatter.
    """
    if data.get("type") is None:
        issues.append(
            error(
                IssueCode.BAD_ERRATUM_TYPE,
                "`type` is required for errata; use technical or editorial",
            )
        )
        kind = None
    else:
        kind = _single(data, "type", fv.parse_erratum_type, issues)
    return ErratumHeader(
        type=kind,
        section=_single(data, "section", fv.parse_text, issues),
        reported_by=_single(data, "reported-by", fv.parse_text, issues),
        reported_date=_single(data, "date", fv.parse_date, issues),
    )


def _erratum_target(
    data: Mapping[str, object], issues: list[Issue]
) -> uuid.UUID | None:
    """
    Validate ``erratum-for``, the UUID of the corrected decision.

    :param data: Frontmatter fields of an erratum.
    :param issues: Issue list to append to.
    :returns: The corrected decision UUID, or ``None``.
    """
    target = _single(data, "erratum-for", fv.parse_uuid, issues)
    if target is None:
        issues.append(
            error(
                IssueCode.ERRATUM_WITHOUT_TARGET,
                "`erratum-for` must be the UUID of the decision this "
                "erratum corrects; the erratum is not linked until it is",
            )
        )
    return target


def _legacy_erratum(data: Mapping[str, object], issues: list[Issue]) -> None:
    """
    Reject the retired ``kind: erratum`` / ``corrects:`` shape.

    :param data: Frontmatter fields.
    :param issues: Issue list to append to.
    """
    if LEGACY_ERRATUM_FIELDS.intersection(data):
        issues.append(
            error(IssueCode.LEGACY_ERRATUM_FORMAT, _LEGACY_ERRATUM_MESSAGE)
        )


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


_UNKNOWN_HINTS = {
    "decision-date": "; errata use `date` for the report date",
    **{
        name: "; it is only used by errata (with `erratum-for`)"
        for name in ERRATUM_FIELDS - DECISION_FIELDS
    },
}


def _unknown_fields(
    data: Mapping[str, object], is_erratum: bool
) -> list[Issue]:
    """
    Report fields the catalog does not understand for this record kind.

    Legacy erratum fields are reported by :func:`_legacy_erratum`.

    :param data: Frontmatter fields.
    :param is_erratum: Whether the record is an erratum.
    :returns: One warning per unknown field.
    """
    allowed = ERRATUM_FIELDS if is_erratum else DECISION_FIELDS
    return [
        warning(
            IssueCode.UNKNOWN_FIELD,
            f"unknown field `{name}` is ignored{_UNKNOWN_HINTS.get(name, '')}",
        )
        for name in data
        if name not in allowed and name not in LEGACY_ERRATUM_FIELDS
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
    is_erratum = "erratum-for" in data
    if is_erratum:
        erratum = _erratum_header(data, issues)
        decision_date = erratum.reported_date
        corrects = _erratum_target(data, issues)
    else:
        erratum = None
        decision_date = _date_field(data, inferred, issues)
        corrects = None
    _legacy_erratum(data, issues)
    links = Links(
        updates=_uuid_list(data, "updates", issues),
        obsoletes=_obsoletes(data, issues),
        corrects=corrects,
    )
    signoff = _signoff(data, issues)
    issues.extend(_unknown_fields(data, is_erratum))
    return FieldValues(
        adr_uuid=adr_uuid,
        title=title,
        decision_date=decision_date,
        erratum=erratum,
        links=links if adr_uuid is not None else Links(),
        legacy_signoff=signoff,
        issues=tuple(issues),
    )
