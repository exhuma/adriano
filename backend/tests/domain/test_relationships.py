"""Tests for relationship resolution (``app.domain.relationships``)."""

import uuid

import pytest

from app.domain.issues import IssueCode, Severity
from app.domain.records import Links, LinkType, RecordKind
from app.domain.relationships import (
    DisplayStatus,
    InboundType,
    RecordSummary,
    RelationshipIndex,
    resolve_relationships,
)

OLD = uuid.UUID("00000000-0000-4000-8000-000000000001")
NEW = uuid.UUID("00000000-0000-4000-8000-000000000002")
FIX = uuid.UUID("00000000-0000-4000-8000-000000000003")
GONE = uuid.UUID("00000000-0000-4000-8000-0000000000ff")


def summary(
    adr_uuid: uuid.UUID,
    *,
    links: Links | None = None,
    kind: RecordKind = RecordKind.DECISION,
) -> RecordSummary:
    """
    Build a record summary for tests.

    :param adr_uuid: Record UUID.
    :param links: Outbound links.
    :param kind: Record kind.
    :returns: The summary.
    """
    return RecordSummary(
        adr_uuid=adr_uuid, links=links or Links(), record_kind=kind
    )


def test_obsoletes_resolves_and_derives_status() -> None:
    """Ensure an obsoleted decision shows the replacing record inbound."""
    old = summary(OLD)
    new = summary(NEW, links=Links(obsoletes=(OLD,)))
    index = RelationshipIndex([old, new])

    view = index.view(OLD)

    assert view.status is DisplayStatus.OBSOLETED
    assert view.inbound_uuids(InboundType.OBSOLETED_BY) == (NEW,)
    assert index.view(NEW).outbound[0].resolved


def test_updates_derives_updated_status() -> None:
    """Ensure an updated decision has status ``updated``."""
    old = summary(OLD)
    new = summary(NEW, links=Links(updates=(OLD,)))

    view = resolve_relationships([old, new], OLD)

    assert view.status is DisplayStatus.UPDATED
    assert view.inbound_uuids(InboundType.UPDATED_BY) == (NEW,)


def test_obsoleted_wins_over_updated() -> None:
    """Ensure obsolescence takes precedence over updates for status."""
    old = summary(OLD)
    upd = summary(NEW, links=Links(updates=(OLD,)))
    rep = summary(FIX, links=Links(obsoletes=(OLD,)))

    view = resolve_relationships([old, upd, rep], OLD)

    assert view.status is DisplayStatus.OBSOLETED


def test_unlinked_record_is_active() -> None:
    """Ensure a record nobody links to is active."""
    view = resolve_relationships([summary(OLD)], OLD)

    assert view.status is DisplayStatus.ACTIVE
    assert view.issues == ()


def test_errata_found_by_reverse_corrects() -> None:
    """Ensure errata are listed on the decision they correct."""
    old = summary(OLD)
    fix = summary(FIX, links=Links(corrects=OLD), kind=RecordKind.ERRATUM)

    view = resolve_relationships([old, fix], OLD)

    assert view.errata == (FIX,)
    assert view.status is DisplayStatus.ACTIVE


def test_corrects_link_of_a_decision_is_not_an_erratum() -> None:
    """Ensure only erratum records count as errata of their target."""
    old = summary(OLD)
    other = summary(NEW, links=Links(corrects=OLD))

    assert resolve_relationships([old, other], OLD).errata == ()


def test_missing_target_is_reported() -> None:
    """Ensure a link to an unknown UUID yields ``missing_target``."""
    new = summary(NEW, links=Links(obsoletes=(GONE,)))

    view = resolve_relationships([new], NEW)

    assert not view.outbound[0].resolved
    [issue] = view.issues
    assert (issue.code, issue.severity) == (
        IssueCode.MISSING_TARGET,
        Severity.WARNING,
    )
    assert str(GONE) in issue.message


def test_self_link_is_not_resolved() -> None:
    """Ensure a record never resolves a link to itself."""
    new = summary(NEW, links=Links(updates=(NEW,)))

    view = resolve_relationships([new], NEW)

    assert not view.outbound[0].resolved
    assert view.inbound == ()


def test_link_resolves_by_uuid_alone() -> None:
    """Ensure a target resolves wherever it lives: UUIDs are global."""
    new = summary(NEW, links=Links(updates=(OLD,), obsoletes=(FIX,)))
    index = RelationshipIndex([summary(OLD), summary(FIX), new])

    view = index.view(NEW)

    assert [(link.target_uuid, link.resolved) for link in view.outbound] == [
        (OLD, True),
        (FIX, True),
    ]
    assert view.issues == ()


def test_two_summaries_for_one_uuid_are_refused() -> None:
    """Ensure the index refuses two summaries of the same ADR."""
    with pytest.raises(ValueError):
        RelationshipIndex([summary(OLD), summary(OLD, links=Links())])


def test_outbound_preserves_link_types() -> None:
    """Ensure outbound links keep their authored relationship types."""
    old = summary(OLD)
    new = summary(NEW, links=Links(updates=(OLD,), obsoletes=(OLD,)))

    view = resolve_relationships([old, new], NEW)

    assert [link.link_type for link in view.outbound] == [
        LinkType.UPDATES,
        LinkType.OBSOLETES,
    ]


def test_unknown_uuid_raises_key_error() -> None:
    """Ensure viewing a UUID outside the index fails loudly."""
    with pytest.raises(KeyError):
        resolve_relationships([summary(OLD)], NEW)
