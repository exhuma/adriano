"""
Parity between the SQL approval state and ``domain.approval.evaluate``.

Every scenario gets its own identity. For each policy variant the state
computed by the store (search items and the ``needs_approval`` filter)
must equal the domain evaluation over the identity's stored events. The
browse path (state joined after paging) and the filtered path (state
joined before paging) are both checked, with and without a text query
and across page boundaries. Erratum rows (:data:`ERRATA`) check that
the ``record_kind`` filter combines with both paths.
"""

import dataclasses
import uuid

import pytest

from app.domain.approval import (
    ApprovalStateCode,
    DecisionAction,
    Policy,
    evaluate,
)
from app.domain.values import Identity, Links, RecordKind
from app.storage.port import (
    MAX_PAGE_SIZE,
    CatalogStore,
    NewDecision,
    SearchFilters,
    SearchItem,
)
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import put_record

A = DecisionAction.ACCEPTED
R = DecisionAction.REJECTED

#: name -> (events as (digest label, action), expected required state).
#: Digest labels: "cur" is the published content, "old"/"old2" other
#: revisions of the same identity. Events are appended in list order.
SCENARIOS: dict[str, tuple[list[tuple[str, DecisionAction]], str]] = {
    "none": ([], "pending"),
    "accepted": ([("cur", A)], "accepted"),
    "rejected": ([("cur", R)], "rejected"),
    "changed": ([("old", A)], "changed_since_acceptance"),
    "old_rejected_only": ([("old", R)], "pending"),
    "old_accepted_cur_rejected": ([("old", A), ("cur", R)], "rejected"),
    "cur_accepted_old_rejected": ([("old", R), ("cur", A)], "accepted"),
    "accepted_then_rejected_other": (
        [("old", A), ("old2", R)],
        "changed_since_acceptance",
    ),
    "rejected_then_accepted_other": (
        [("old", R), ("old2", A)],
        "changed_since_acceptance",
    ),
    "two_old_rejected": ([("old", R), ("old2", R)], "pending"),
    "three_digests_cur_accepted": (
        [("old", A), ("old2", R), ("cur", A)],
        "accepted",
    ),
    "three_digests_cur_rejected": (
        [("old", R), ("old2", A), ("cur", R)],
        "rejected",
    ),
}

#: Identities with several rows. name -> (rows as ref -> content label,
#: events as (content label, action), expected required state per ref).
#: Ref "main" is the published row, any other ref a candidate.
MULTI_ROW: dict[
    str,
    tuple[
        dict[str, str],
        list[tuple[str, DecisionAction]],
        dict[str, str],
    ],
] = {
    "candidate_accepted_published_diverged": (
        {"main": "pub", "feature": "cand"},
        [("cand", A)],
        {"main": "changed_since_acceptance", "feature": "accepted"},
    ),
    "published_rejected_candidate_accepted": (
        {"main": "pub", "feature": "cand"},
        [("pub", R), ("cand", A)],
        {"main": "rejected", "feature": "accepted"},
    ),
    "published_accepted_candidate_undecided": (
        {"main": "pub", "feature": "cand"},
        [("pub", A)],
        {"main": "accepted", "feature": "changed_since_acceptance"},
    ),
    "competing_candidates": (
        {"main": "pub", "feature-a": "a", "feature-b": "b"},
        [("a", A), ("b", R)],
        {
            "main": "changed_since_acceptance",
            "feature-a": "accepted",
            "feature-b": "rejected",
        },
    ),
    "candidate_only_rejected": (
        {"feature": "cand"},
        [("cand", R)],
        {"feature": "rejected"},
    ),
    "promoted": (
        {"main": "same", "feature": "same"},
        [("same", A)],
        {"main": "accepted", "feature": "accepted"},
    ),
}

#: Rows outside the scenario identities: an accepted copy of the "none"
#: UUID in another project and in another registration.
ELSEWHERE = (("central", "elsewhere"), ("other", "platform"))

#: Published erratum identities. name -> (events on the current
#: content, expected required state).
ERRATA: dict[str, tuple[list[DecisionAction], str]] = {
    "erratum_reported": ([], "pending"),
    "erratum_verified": ([A], "accepted"),
    "erratum_rejected": ([R], "rejected"),
}

ROW_COUNT = (
    len(SCENARIOS)
    + sum(len(rows) for rows, _, _ in MULTI_ROW.values())
    + len(ELSEWHERE)
    + len(ERRATA)
)

POLICIES = {
    "missing": None,
    "not_required": Policy(id="global", version=1, required=False),
    "required": Policy(id="global", version=1),
}


def scenario_uuid(name: str) -> uuid.UUID:
    """
    Derive the stable UUID of a scenario identity.

    :param name: Scenario name.
    :returns: The UUID.
    """
    return uuid.uuid5(uuid.NAMESPACE_URL, name)


def _decide(
    store: CatalogStore, identity: Identity, digest: str, action: str
) -> None:
    """
    Append one decision.

    :param store: Store.
    :param identity: Identity.
    :param digest: Digest.
    :param action: Action value.
    """
    store.append_decision(
        NewDecision(
            identity=identity,
            adr_uuid=uuid.UUID(identity.record_key),
            digest=digest,
            action=DecisionAction(action),
            actor_issuer="iss",
            actor_subject="sub",
            actor_display=None,
            actor_email=None,
            comment=None,
            policy_id="global",
            policy_version=1,
        )
    )


def _store_single(store: CatalogStore) -> None:
    """
    Store one published record plus its events per :data:`SCENARIOS`.

    :param store: Store in the current unit of work.
    """
    for name, (events, _) in SCENARIOS.items():
        adr_uuid = scenario_uuid(name)
        digests = {
            label: put_record(
                store, adr_uuid=adr_uuid, body=f"{label} {name}"
            ).digest
            for label in ("old", "old2")
        }
        cur = put_record(
            store, adr_uuid=adr_uuid, path=f"{name}.md", title=name
        )
        store.upsert_published(cur)
        digests["cur"] = cur.digest
        for label, action in events:
            _decide(store, cur.identity, digests[label], action)


def _store_multi(store: CatalogStore) -> None:
    """
    Store the rows and events of every :data:`MULTI_ROW` identity.

    Rows carry the title ``<name>/<content label>`` and the body word
    ``divergent``, so rows with one label have identical content.

    :param store: Store in the current unit of work.
    """
    for name, (rows, events, _) in MULTI_ROW.items():
        digests: dict[str, str] = {}
        identity = None
        for ref, label in rows.items():
            write = put_record(
                store,
                adr_uuid=scenario_uuid(name),
                path=f"{name}.md",
                ref=ref,
                title=f"{name}/{label}",
                body=f"divergent {label}",
            )
            if ref == "main":
                store.upsert_published(write)
            else:
                store.upsert_candidate(write)
            digests[label] = write.digest
            identity = write.identity
        assert identity is not None
        for label, action in events:
            _decide(store, identity, digests[label], action)


def _store_errata(store: CatalogStore) -> None:
    """
    Store the published erratum rows of :data:`ERRATA`.

    Each corrects the "none" scenario and carries the body word
    ``divergent``, so text queries reach them too.

    :param store: Store in the current unit of work.
    """
    for name, (actions, _) in ERRATA.items():
        write = dataclasses.replace(
            put_record(
                store,
                adr_uuid=scenario_uuid(name),
                path=f"errata/{name}.md",
                title=name,
                body=f"divergent {name}",
            ),
            record_kind=RecordKind.ERRATUM,
            links=Links(corrects=scenario_uuid("none")),
        )
        store.upsert_published(write)
        for action in actions:
            _decide(store, write.identity, write.digest, action)


@pytest.fixture
def scenarios(provider: PostgresStoreProvider) -> PostgresStoreProvider:
    """
    Store every single-row and multi-row scenario.

    Also stores accepted copies of the "none" record in another project
    and another registration (different identities, which must not leak
    into "none").

    :param provider: Clean provider.
    :returns: The provider.
    """
    with provider.unit_of_work() as store:
        _store_single(store)
        _store_multi(store)
        _store_errata(store)
        for source_id, project in ELSEWHERE:
            elsewhere = put_record(
                store,
                source_id=source_id,
                adr_uuid=scenario_uuid("none"),
                project=project,
                path="none.md",
                title="none",
            )
            store.upsert_published(elsewhere)
            _decide(store, elsewhere.identity, elsewhere.digest, A)
    return provider


def _all_pages(
    store: CatalogStore,
    query: str | None,
    filters: SearchFilters,
    policy: Policy | None,
    page_size: int,
) -> list[SearchItem]:
    """
    Collect every page of a search.

    :param store: Store.
    :param query: Text query.
    :param filters: Filters.
    :param policy: Policy.
    :param page_size: Page size.
    :returns: The items of all pages, in order.
    """
    items: list[SearchItem] = []
    page = 1
    while True:
        result = store.search(query, filters, page, page_size, policy=policy)
        items += result.items
        if page * page_size >= result.total:
            assert len(items) == result.total
            return items
        page += 1


@pytest.mark.parametrize("query", [None, "divergent", "body"])
@pytest.mark.parametrize("policy_name", list(POLICIES))
def test_sql_state_matches_domain(
    scenarios: PostgresStoreProvider, policy_name: str, query: str | None
) -> None:
    """Ensure every row's SQL state equals the domain evaluation."""
    policy = POLICIES[policy_name]
    with scenarios.unit_of_work() as store:
        page = store.search(
            query, SearchFilters(), 1, MAX_PAGE_SIZE, policy=policy
        )
        needs = store.search(
            query,
            SearchFilters(needs_approval=True),
            1,
            MAX_PAGE_SIZE,
            policy=policy,
        )
        expected = {}
        for item in page.items:
            events = store.list_decisions(
                Identity(item.source_id, item.project, item.record_key)
            )
            expected[item.id] = evaluate(
                policy,
                [event.as_view() for event in events],
                item.digest,
                approvable=True,
            )
    assert page.items
    if query is None:
        assert page.total == ROW_COUNT
    for item in page.items:
        assert item.approval_state is expected[item.id].state, item.title
    assert [item.id for item in needs.items] == [
        item.id for item in page.items if expected[item.id].needs_approval
    ]
    assert {item.id: item.approval_state for item in needs.items} == {
        item.id: item.approval_state
        for item in page.items
        if expected[item.id].needs_approval
    }
    assert needs.total == len(needs.items)


@pytest.mark.parametrize("needs_approval", [False, True])
@pytest.mark.parametrize("policy_name", list(POLICIES))
def test_small_pages_match_one_large_page(
    scenarios: PostgresStoreProvider, policy_name: str, needs_approval: bool
) -> None:
    """Ensure paging yields the same rows, order and states."""
    policy = POLICIES[policy_name]
    filters = SearchFilters(needs_approval=needs_approval)
    with scenarios.unit_of_work() as store:
        whole = store.search(None, filters, 1, MAX_PAGE_SIZE, policy=policy)
        paged = _all_pages(store, None, filters, policy, page_size=4)
    assert paged == list(whole.items)


def test_fixture_covers_every_required_state(
    scenarios: PostgresStoreProvider,
) -> None:
    """Ensure the fixture exercises the expected state per scenario."""
    with scenarios.unit_of_work() as store:
        page = store.search(
            None,
            SearchFilters(),
            1,
            MAX_PAGE_SIZE,
            policy=POLICIES["required"],
        )
    by_location = {
        (item.source_id, item.project, item.title): item.approval_state
        for item in page.items
    }
    for name, (_, state) in SCENARIOS.items():
        assert by_location["central", "platform", name] == state, name
    by_ref = {
        (item.record_key, item.ref): item.approval_state for item in page.items
    }
    for name, (_, _, states) in MULTI_ROW.items():
        for ref, state in states.items():
            key = (str(scenario_uuid(name)), ref)
            assert by_ref[key] == state, (name, ref)
    for source_id, project in ELSEWHERE:
        state = by_location[source_id, project, "none"]
        assert state is ApprovalStateCode.ACCEPTED


@pytest.mark.parametrize("query", [None, "divergent"])
@pytest.mark.parametrize("needs_approval", [False, True])
@pytest.mark.parametrize(
    "record_kind", [None, RecordKind.DECISION, RecordKind.ERRATUM]
)
@pytest.mark.parametrize("policy_name", list(POLICIES))
def test_record_kind_filter_matches_unfiltered_rows(
    scenarios: PostgresStoreProvider,
    policy_name: str,
    record_kind: RecordKind | None,
    needs_approval: bool,
    query: str | None,
) -> None:
    """Ensure the kind filter keeps exactly the matching rows and states."""
    policy = POLICIES[policy_name]
    unfiltered = SearchFilters(needs_approval=needs_approval)
    filtered = SearchFilters(
        needs_approval=needs_approval, record_kind=record_kind
    )
    with scenarios.unit_of_work() as store:
        whole = _all_pages(store, query, unfiltered, policy, MAX_PAGE_SIZE)
        paged = _all_pages(store, query, filtered, policy, page_size=4)
    expected = [
        item
        for item in whole
        if record_kind is None or item.record_kind is record_kind
    ]
    assert paged == expected
    if record_kind is RecordKind.ERRATUM and not needs_approval:
        assert len(paged) == len(ERRATA)


def test_fixture_covers_every_erratum_state(
    scenarios: PostgresStoreProvider,
) -> None:
    """Ensure each erratum row has its expected state and target."""
    filters = SearchFilters(record_kind=RecordKind.ERRATUM)
    with scenarios.unit_of_work() as store:
        page = store.search(
            None, filters, 1, MAX_PAGE_SIZE, policy=POLICIES["required"]
        )
    states = {item.title: item.approval_state.value for item in page.items}
    assert states == {name: state for name, (_, state) in ERRATA.items()}
    assert {item.corrects for item in page.items} == {scenario_uuid("none")}
