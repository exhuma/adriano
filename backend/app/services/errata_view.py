"""
Errata part of the record detail page (read-only).

Converts the erratum rows that belong to a record (resolved by
:mod:`app.services.record_relationships`) into :class:`ErratumInfo`
values, each with the approval state of the erratum's **own**
identity and digest, and counts them in :class:`ErrataSummary` for
the page's top notice. The corrected record's own digest, approval
state and history are never involved: an erratum is a separate record
with its own accept/reject workflow.

Approval state per erratum uses :func:`app.domain.approval.evaluate`
with the same ``approvable`` rule as the record detail
(:func:`app.services.approval_view.is_approvable`). The decision events
of all errata are read with **one** query
(:meth:`~app.storage.port.CatalogStore.list_decisions_for`), so the
detail endpoint's query count does not grow with the number of errata.

Summary counts (published errata only; candidates are proposals and
are counted in ``proposed``):

- ``accepted`` -> ``verified``;
- ``not_required`` -> ``verified`` as well: the policy requires no
  review, so a published erratum stands as published (the raw
  ``approval_state`` stays on each item so the UI can label it
  precisely);
- ``rejected`` -> ``rejected``;
- ``changed_since_acceptance`` -> ``changed`` (verified content was
  edited; not counted as verified);
- ``pending`` and ``policy_missing`` -> ``reported``.

``total`` is ``verified + reported + rejected + changed``.

Public API: :class:`ErratumContentInfo`, :class:`ErratumInfo`,
:class:`ErrataSummary`, :class:`ErrataView`, :func:`erratum_content`,
:func:`build_errata`.
"""

import datetime
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.domain.approval import (
    ApprovalStateCode,
    DecisionEventView,
    Policy,
    evaluate,
)
from app.domain.errata import ErratumType
from app.domain.values import Identity
from app.services.approval_view import is_approvable
from app.storage.port import (
    CatalogStore,
    ErratumRow,
    RecordState,
    StoredErratum,
)

__all__ = [
    "ErrataSummary",
    "ErrataView",
    "ErratumContentInfo",
    "ErratumInfo",
    "build_errata",
    "erratum_content",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class ErratumContentInfo:
    """
    The structured content of one erratum.

    :param type: ``technical`` or ``editorial``, ``None`` if invalid.
    :param section: Where in the decision the error is, if given.
    :param reported_by: Free-text reporter (informational only).
    :param reported_date: Authored report date, if valid.
    :param original_html: Sanitized "Original text" HTML, if any.
    :param corrected_html: Sanitized "Corrected text" HTML.
    :param notes_html: Sanitized notes HTML, if any.
    """

    type: ErratumType | None
    section: str | None
    reported_by: str | None
    reported_date: datetime.date | None
    original_html: str | None
    corrected_html: str
    notes_html: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ErratumInfo:
    """
    One erratum (published or candidate) of the viewed record.

    Content fields are ``None`` (and ``corrected_html`` empty) when the
    row was stored before erratum content was (``has_content`` false).

    :param id: Erratum record id.
    :param kind: ``published`` or ``candidate`` (a proposal).
    :param ref: Branch/ref of the erratum content.
    :param source_id: Registration id of the erratum.
    :param project: Project path of the erratum.
    :param path: File path of the erratum.
    :param title: Erratum display title.
    :param type: Erratum type.
    :param section: Section of the decision, if given.
    :param reported_by: Free-text reporter.
    :param reported_date: Report date.
    :param original_html: "Original text" HTML.
    :param corrected_html: "Corrected text" HTML.
    :param notes_html: Notes HTML.
    :param approval_state: Approval state of the erratum's own digest.
    :param digest: The erratum's current digest.
    :param updated_at: When the erratum's content last changed.
    :param has_content: Whether structured content is stored.
    """

    id: uuid.UUID
    kind: RecordState
    ref: str
    source_id: str
    project: str
    path: str
    title: str
    type: ErratumType | None
    section: str | None
    reported_by: str | None
    reported_date: datetime.date | None
    original_html: str | None
    corrected_html: str
    notes_html: str | None
    approval_state: ApprovalStateCode
    digest: str
    updated_at: datetime.datetime
    has_content: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrataSummary:
    """
    Errata counts for the top notice; see the module docstring.

    :param total: Published errata.
    :param verified: Published errata accepted (or not requiring
        review).
    :param reported: Published errata awaiting review.
    :param rejected: Published errata rejected.
    :param changed: Published errata changed since acceptance.
    :param proposed: Candidate (proposed) errata.
    """

    total: int
    verified: int
    reported: int
    rejected: int
    changed: int
    proposed: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrataView:
    """
    The errata of one record with their summary.

    :param errata: Published errata first, then candidates.
    :param summary: Counts.
    """

    errata: tuple[ErratumInfo, ...]
    summary: ErrataSummary


_BUCKET: dict[ApprovalStateCode, str] = {
    ApprovalStateCode.ACCEPTED: "verified",
    ApprovalStateCode.NOT_REQUIRED: "verified",
    ApprovalStateCode.REJECTED: "rejected",
    ApprovalStateCode.CHANGED_SINCE_ACCEPTANCE: "changed",
    ApprovalStateCode.PENDING: "reported",
    ApprovalStateCode.POLICY_MISSING: "reported",
}


def erratum_content(
    erratum: StoredErratum | None,
) -> ErratumContentInfo | None:
    """
    Convert stored erratum content for the API.

    :param erratum: Stored content, or ``None``.
    :returns: The content, or ``None``.
    """
    if erratum is None:
        return None
    return ErratumContentInfo(
        type=erratum.type,
        section=erratum.section,
        reported_by=erratum.reported_by,
        reported_date=erratum.reported_date,
        original_html=erratum.original_html,
        corrected_html=erratum.corrected_html,
        notes_html=erratum.notes_html,
    )


def _info(row: ErratumRow, state: ApprovalStateCode) -> ErratumInfo:
    """
    Build one :class:`ErratumInfo`.

    :param row: The erratum row.
    :param state: Its approval state.
    :returns: The value.
    """
    content = row.erratum
    return ErratumInfo(
        id=row.id,
        kind=row.kind,
        ref=row.ref,
        source_id=row.source_id,
        project=row.project,
        path=row.path,
        title=row.title,
        type=content.type if content else None,
        section=content.section if content else None,
        reported_by=content.reported_by if content else None,
        reported_date=content.reported_date if content else None,
        original_html=content.original_html if content else None,
        corrected_html=content.corrected_html if content else "",
        notes_html=content.notes_html if content else None,
        approval_state=state,
        digest=row.digest,
        updated_at=row.updated_at,
        has_content=content is not None,
    )


def _summary(errata: Iterable[ErratumInfo]) -> ErrataSummary:
    """
    Count errata for the top notice.

    :param errata: The record's errata.
    :returns: The counts.
    """
    counts: dict[str, int] = dict.fromkeys(
        ("verified", "reported", "rejected", "changed"), 0
    )
    proposed = 0
    for item in errata:
        if item.kind is RecordState.CANDIDATE:
            proposed += 1
        else:
            counts[_BUCKET[item.approval_state]] += 1
    return ErrataSummary(
        total=sum(counts.values()), proposed=proposed, **counts
    )


def build_errata(
    store: CatalogStore,
    rows: Sequence[ErratumRow],
    policy: Policy | None,
) -> ErrataView:
    """
    Evaluate the approval state of each erratum and count them.

    :param store: Store of the caller's unit of work.
    :param rows: Erratum rows that belong to the viewed record.
    :param policy: The configured policy, or ``None``.
    :returns: The errata and their summary.
    """
    identities = {row.identity for row in rows}
    events: dict[Identity, list[DecisionEventView]] = defaultdict(list)
    for event in store.list_decisions_for(identities):
        events[event.identity].append(event.as_view())
    errata = tuple(
        _info(
            row,
            evaluate(
                policy, events[row.identity], row.digest, is_approvable(row)
            ).state,
        )
        for row in rows
    )
    return ErrataView(errata=errata, summary=_summary(errata))
