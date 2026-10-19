"""Tests for relationship resolution (``app.domain.relationships``)."""

import dataclasses
import datetime
import uuid

import pytest

from app.domain.issues import IssueCode, Severity
from app.domain.records import Identity, Links, LinkType, RecordKind
from app.domain.relationships import (
    DisplayStatus,
    InboundType,
    RecordSummary,
    RelationshipIndex,
    Resolution,
    resolve_relationships,
)

OLD = uuid.UUID("00000000-0000-4000-8000-000000000001")
NEW = uuid.UUID("00000000-0000-4000-8000-000000000002")
FIX = uuid.UUID("00000000-0000-4000-8000-000000000003")
GONE = uuid.UUID("00000000-0000-4000-8000-0000000000ff")


def summary(
    key: str,
    adr_uuid: uuid.UUID | None,
    *,
    source: str = "central",
    project: str = "platform",
    links: Links | None = None,
    kind: RecordKind = RecordKind.DECISION,
) -> RecordSummary:
    """
    Build a record summary for tests.

    :param key: Row key.
    :param adr_uuid: Record UUID.
    :param source: Registration id.
    :param project: Project path.
    :param links: Outbound links.
    :param kind: Record kind.
    :returns: The summary.
    """
    record_key = str(adr_uuid) if adr_uuid else f"src:{source}/{key}"
    return RecordSummary(
        key=key,
        identity=Identity(source, project, record_key),
        adr_uuid=adr_uuid,
        links=links or Links(),
        record_kind=kind,
        path=f"doc/decisions/{key}.md",
    )


def test_obsoletes_resolves_and_derives_status() -> None:
    """Ensure an obsoleted decision shows the replacing record inbound."""
    old = summary("old", OLD)
    new = summary("new", NEW, links=Links(obsoletes=(OLD,)))
    index = RelationshipIndex([old, new])

    view = index.view("old")

    assert view.status is DisplayStatus.OBSOLETED
    assert view.inbound_keys(InboundType.OBSOLETED_BY) == ("new",)
    assert index.view("new").outbound[0].target_key == "old"


def test_updates_derives_updated_status() -> None:
    """Ensure an updated decision has status ``updated``."""
    old = summary("old", OLD)
    new = summary("new", NEW, links=Links(updates=(OLD,)))

    view = resolve_relationships([old, new], "old")

    assert view.status is DisplayStatus.UPDATED
    assert view.inbound_keys(InboundType.UPDATED_BY) == ("new",)


def test_obsoleted_wins_over_updated() -> None:
    """Ensure obsolescence takes precedence over updates for status."""
    old = summary("old", OLD)
    upd = summary("upd", NEW, links=Links(updates=(OLD,)))
    rep = summary("rep", FIX, links=Links(obsoletes=(OLD,)))

    view = resolve_relationships([old, upd, rep], "old")

    assert view.status is DisplayStatus.OBSOLETED


def test_unlinked_record_is_active() -> None:
    """Ensure a record nobody links to is active."""
    view = resolve_relationships([summary("old", OLD)], "old")

    assert view.status is DisplayStatus.ACTIVE
    assert view.issues == ()


def test_errata_found_by_reverse_corrects() -> None:
    """Ensure errata are listed on the decision they correct."""
    old = summary("old", OLD)
    fix = summary(
        "fix", FIX, links=Links(corrects=OLD), kind=RecordKind.ERRATUM
    )

    view = resolve_relationships([old, fix], "old")

    assert view.errata == ("fix",)
    assert view.status is DisplayStatus.ACTIVE


def test_missing_target_is_reported() -> None:
    """Ensure a link to an unknown UUID yields ``missing_target``."""
    new = summary("new", NEW, links=Links(obsoletes=(GONE,)))

    view = resolve_relationships([new], "new")

    assert view.outbound[0].target_key is None
    assert [i.code for i in view.issues] == [IssueCode.MISSING_TARGET]
    assert str(GONE) in view.issues[0].message


def test_self_link_is_not_resolved() -> None:
    """Ensure a record never resolves a link to itself."""
    new = summary("new", NEW, links=Links(updates=(NEW,)))

    view = resolve_relationships([new], "new")

    assert view.outbound[0].target_key is None


@pytest.mark.parametrize(
    ("near_source", "near_project", "tier"),
    [
        ("central", "platform", Resolution.SAME_PROJECT),
        ("central", "payments", Resolution.SAME_REGISTRATION),
    ],
)
def test_resolution_prefers_closest_target(
    near_source: str, near_project: str, tier: Resolution
) -> None:
    """Ensure links prefer same project, then same registration."""
    near = summary("near", OLD, source=near_source, project=near_project)
    far = summary("far", OLD, source="gitlab", project="other")
    new = summary("new", NEW, links=Links(updates=(OLD,)))

    link = resolve_relationships([near, far, new], "new").outbound[0]

    assert (link.target_key, link.resolution) == ("near", tier)


def test_global_resolution() -> None:
    """Ensure links resolve across registrations as a last resort."""
    far = summary("far", OLD, source="gitlab", project="other")
    new = summary("new", NEW, links=Links(updates=(OLD,)))

    link = resolve_relationships([far, new], "new").outbound[0]

    assert link.resolution is Resolution.GLOBAL


def test_ambiguous_target_is_reported_not_picked() -> None:
    """Ensure two equally close targets leave the link unresolved."""
    a = summary("a", OLD, source="gitlab", project="x")
    b = summary("b", OLD, source="gitlab", project="y")
    new = summary("new", NEW, links=Links(obsoletes=(OLD,)))
    index = RelationshipIndex([a, b, new])

    view = index.view("new")

    assert view.outbound[0].target_key is None
    assert view.outbound[0].candidates == ("a", "b")
    assert IssueCode.AMBIGUOUS_TARGET in [i.code for i in view.issues]
    assert index.view("a").status is DisplayStatus.ACTIVE


def test_duplicate_uuid_across_identities_is_a_warning() -> None:
    """Ensure the same UUID in another project is flagged as a warning."""
    a = summary("a", OLD, project="platform")
    b = summary("b", OLD, project="payments")

    view = resolve_relationships([a, b], "a")

    (issue,) = view.issues
    assert (issue.code, issue.severity) == (
        IssueCode.DUPLICATE_UUID,
        Severity.WARNING,
    )
    assert "central/payments/doc/decisions/b.md" in issue.message


def test_duplicate_uuid_within_identity_is_an_error() -> None:
    """Ensure two files with one UUID in one project are an error."""
    a = summary("a", OLD)
    b = summary("b", OLD)

    view = resolve_relationships([a, b], "a")

    (issue,) = view.issues
    assert (issue.code, issue.severity) == (
        IssueCode.DUPLICATE_UUID,
        Severity.ERROR,
    )


def test_record_without_uuid_has_no_relationships() -> None:
    """Ensure UUID-less records neither link nor get linked."""
    bare = summary("bare", None, links=Links(updates=(OLD,)))
    old = summary("old", OLD)

    view = resolve_relationships([bare, old], "bare")

    assert view.outbound == ()
    assert resolve_relationships([bare, old], "old").inbound == ()


def test_duplicate_keys_are_refused() -> None:
    """Ensure the index refuses two summaries with the same key."""
    with pytest.raises(ValueError):
        RelationshipIndex([summary("a", OLD), summary("a", NEW)])


def test_outbound_preserves_link_types() -> None:
    """Ensure outbound links keep their authored relationship types."""
    old = summary("old", OLD)
    new = summary("new", NEW, links=Links(updates=(OLD,), obsoletes=(OLD,)))

    view = resolve_relationships([old, new], "new")

    assert [link.link_type for link in view.outbound] == [
        LinkType.UPDATES,
        LinkType.OBSOLETES,
    ]


def revision(
    of: RecordSummary,
    key: str,
    *,
    updated_at: datetime.datetime | None = None,
    links: Links | None = None,
) -> RecordSummary:
    """
    Build a candidate row of the same identity as *of*.

    :param of: The row whose identity the candidate shares.
    :param key: Row key of the candidate.
    :param updated_at: When the candidate last changed.
    :param links: Outbound links (default: those of *of*).
    :returns: The candidate summary.
    """
    return dataclasses.replace(
        of,
        key=key,
        published=False,
        updated_at=updated_at,
        links=of.links if links is None else links,
    )


T1 = datetime.datetime(2024, 3, 1, tzinfo=datetime.UTC)
T2 = datetime.datetime(2024, 3, 2, tzinfo=datetime.UTC)


def test_candidate_of_same_identity_is_not_a_duplicate() -> None:
    """Ensure a published row and its candidate are revisions, not dupes."""
    published = summary("pub", OLD)
    candidate = revision(published, "cand", updated_at=T1)
    index = RelationshipIndex([published, candidate])

    assert index.view("pub").issues == ()
    assert index.view("cand").issues == ()


def test_two_published_paths_same_uuid_are_a_duplicate_error() -> None:
    """Ensure two published files claiming one UUID stay an error."""
    a = summary("a", OLD)
    b = summary("b", OLD)
    candidate = revision(a, "cand", updated_at=T1)

    view = resolve_relationships([a, b, candidate], "a")

    (issue,) = view.issues
    assert (issue.code, issue.severity) == (
        IssueCode.DUPLICATE_UUID,
        Severity.ERROR,
    )
    assert "doc/decisions/b.md" in issue.message
    assert "decisions/a.md" not in issue.message


def test_cross_project_duplicate_is_still_a_warning_with_candidates() -> None:
    """Ensure another project's UUID reuse warns once despite revisions."""
    a = summary("a", OLD, project="platform")
    candidate = revision(a, "a-cand", updated_at=T1)
    b = summary("b", OLD, project="payments")

    view = resolve_relationships([a, candidate, b], "a")

    (issue,) = view.issues
    assert (issue.code, issue.severity) == (
        IssueCode.DUPLICATE_UUID,
        Severity.WARNING,
    )
    assert "central/payments/doc/decisions/b.md" in issue.message


def test_link_to_identity_with_candidate_prefers_published() -> None:
    """Ensure a target with revisions resolves to its published row."""
    old = summary("old", OLD)
    candidate = revision(old, "old-cand", updated_at=T2)
    new = summary("new", NEW, links=Links(obsoletes=(OLD,)))
    index = RelationshipIndex([old, candidate, new])

    link = index.view("new").outbound[0]

    assert (link.target_key, link.resolution) == (
        "old",
        Resolution.SAME_PROJECT,
    )
    assert not link.ambiguous
    assert index.view("new").issues == ()
    assert index.view("old").status is DisplayStatus.OBSOLETED


def test_link_to_unpublished_identity_picks_latest_candidate() -> None:
    """Ensure an unpublished target resolves to its newest candidate."""
    first = revision(summary("x", OLD), "older", updated_at=T1)
    second = revision(first, "newer", updated_at=T2)
    new = summary("new", NEW, links=Links(updates=(OLD,)))

    view = resolve_relationships([first, second, new], "new")

    assert view.outbound[0].target_key == "newer"
    assert view.issues == ()


def test_revisions_do_not_link_to_each_other() -> None:
    """Ensure a candidate never resolves a link to its published row."""
    published = summary("pub", OLD)
    candidate = revision(
        published, "cand", updated_at=T1, links=Links(updates=(OLD,))
    )

    view = resolve_relationships([published, candidate], "cand")

    assert view.outbound[0].target_key is None
    assert resolve_relationships([published, candidate], "pub").inbound == ()
