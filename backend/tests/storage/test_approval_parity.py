"""
Parity between the SQL approval state and ``domain.approval.evaluate``.

Every scenario gets its own identity. For each policy variant the state
computed by the store (search items and the ``needs_approval`` filter)
must equal the domain evaluation over the identity's stored events.
"""

import uuid

import pytest

from app.domain.approval import (
    ApprovalStateCode,
    DecisionAction,
    Policy,
    evaluate,
)
from app.domain.values import Identity
from app.storage.port import (
    MAX_PAGE_SIZE,
    CatalogStore,
    NewDecision,
    SearchFilters,
)
from app.storage.postgres.store import PostgresStoreProvider
from tests.storage.conftest import put_record

A = DecisionAction.ACCEPTED
R = DecisionAction.REJECTED

#: name -> (events as (digest label, action), expected required state).
#: Digest labels: "cur" is the record's content, "old" another revision.
SCENARIOS: dict[str, tuple[list[tuple[str, DecisionAction]], str]] = {
    "none": ([], "pending"),
    "accepted": ([("cur", A)], "accepted"),
    "rejected": ([("cur", R)], "rejected"),
    "changed": ([("old", A)], "changed_since_acceptance"),
    "old_rejected_only": ([("old", R)], "pending"),
    "old_accepted_cur_rejected": ([("old", A), ("cur", R)], "rejected"),
    "cur_accepted_old_rejected": ([("old", R), ("cur", A)], "accepted"),
}

SCENARIOS_UUID = {
    name: uuid.uuid5(uuid.NAMESPACE_URL, name) for name in SCENARIOS
}


POLICIES = {
    "missing": None,
    "not_required": Policy(id="global", version=1, required=False),
    "required": Policy(id="global", version=1),
}


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


@pytest.fixture
def scenarios(provider: PostgresStoreProvider) -> PostgresStoreProvider:
    """
    Store one published record plus its events per scenario.

    Also stores an accepted candidate whose identical content is
    published (implicit promotion), and an accepted copy of the "none"
    record in another project (a different identity, which must not
    leak into "none").

    :param provider: Clean provider.
    :returns: The provider.
    """
    with provider.unit_of_work() as store:
        for name, (events, _) in SCENARIOS.items():
            adr_uuid = SCENARIOS_UUID[name]
            old = put_record(store, adr_uuid=adr_uuid, body=f"old {name}")
            cur = put_record(
                store, adr_uuid=adr_uuid, path=f"{name}.md", title=name
            )
            store.upsert_published(cur)
            digests = {"cur": cur.digest, "old": old.digest}
            for label, action in events:
                _decide(store, cur.identity, digests[label], action)
        promoted = uuid.uuid5(uuid.NAMESPACE_URL, "promoted")
        candidate = put_record(store, adr_uuid=promoted, ref="feature")
        store.upsert_candidate(candidate)
        store.upsert_published(put_record(store, adr_uuid=promoted))
        _decide(store, candidate.identity, candidate.digest, A)
        elsewhere = put_record(
            store,
            adr_uuid=SCENARIOS_UUID["none"],
            project="elsewhere",
            path="none.md",
            title="none",
        )
        store.upsert_published(elsewhere)
        _decide(store, elsewhere.identity, elsewhere.digest, A)
    return provider


@pytest.mark.parametrize("policy_name", list(POLICIES))
def test_sql_state_matches_domain(
    scenarios: PostgresStoreProvider, policy_name: str
) -> None:
    """Ensure every row's SQL state equals the domain evaluation."""
    policy = POLICIES[policy_name]
    with scenarios.unit_of_work() as store:
        page = store.search(
            None, SearchFilters(), 1, MAX_PAGE_SIZE, policy=policy
        )
        needs = store.search(
            None,
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
    assert page.total == len(SCENARIOS) + 3
    for item in page.items:
        assert item.approval_state is expected[item.id].state, item.title
    assert {item.id for item in needs.items} == {
        key for key, state in expected.items() if state.needs_approval
    }
    assert needs.total == len(needs.items)


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
    platform = [item for item in page.items if item.project == "platform"]
    by_title = {item.title: item.approval_state for item in platform}
    for name, (_, state) in SCENARIOS.items():
        assert by_title[name] == state, name
    promoted = [
        item.approval_state for item in platform if item.title == "A decision"
    ]
    assert promoted == [ApprovalStateCode.ACCEPTED] * 2
    (elsewhere,) = [i for i in page.items if i.project == "elsewhere"]
    assert elsewhere.approval_state is ApprovalStateCode.ACCEPTED
