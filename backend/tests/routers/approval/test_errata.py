"""
Errata on the record detail page and in search, end to end.

Errata are seeded through the shared ingest path (published) or pushed
through the real intake route (candidates), and verified or rejected
through ``POST /api/v1/records/{id}/decisions`` on the **erratum**
record. The corrected decision's digest, approval and history never
change.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, event

from app.config import Settings
from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.approval.support import as_user, candidate, decide, push
from tests.routers.conftest import adr, seed

TARGET = uuid.UUID("7a1e0000-0000-4000-8000-000000000001")
ERRATUM_A = uuid.UUID("7a1e0000-0000-4000-8000-0000000000a1")
ERRATUM_B = uuid.UUID("7a1e0000-0000-4000-8000-0000000000b1")
ERRATUM_C = uuid.UUID("7a1e0000-0000-4000-8000-0000000000c1")
DECISION_PATH = "doc/decisions/2024-01-01-use-a-queue.md"


def erratum_text(
    own: uuid.UUID,
    target: uuid.UUID = TARGET,
    *,
    section: str = "Consequences",
    erratum_type: str = "technical",
) -> str:
    """
    Render an erratum document in the dedicated format.

    :param own: The erratum's own UUID.
    :param target: UUID of the corrected decision.
    :param section: Section line.
    :param erratum_type: ``technical`` or ``editorial``.
    :returns: The text.
    """
    return (
        f"---\nuuid: {own}\nerratum-for: {target}\ntype: {erratum_type}\n"
        f"section: {section}\nreported-by: alice@example.com\n"
        "date: 2024-04-01\n---\n"
        "## Original text\n\nOld words.\n\n"
        "## Corrected text\n\nNew words.\n\n"
        "## Notes\n\nWhy it changed.\n"
    )


def _seed_target(
    provider: PostgresStoreProvider, errata: int = 1, project: str = "platform"
) -> tuple[str, list[str]]:
    """
    Seed the published target decision and *errata* published errata.

    :param provider: Store provider.
    :param errata: Number of published errata to seed.
    :param project: Project of the target and its errata.
    :returns: Target id and erratum ids.
    """
    ids: list[str] = []
    with provider.lock_registration("central") as store:
        target = seed(
            store,
            project=project,
            path=DECISION_PATH,
            content=adr(TARGET, title="Use a queue"),
        )
        for number in range(errata):
            own = uuid.uuid5(TARGET, f"erratum-{number}")
            record_id = seed(
                store,
                project=project,
                path=f"doc/decisions/errata/2024-04-0{number + 1}-fix.md",
                content=erratum_text(own, section=f"S{number}").encode(),
            )
            ids.append(str(record_id))
    return str(target), ids


def _detail(client: TestClient, record_id: str) -> dict[str, Any]:
    """Read a record detail."""
    response = client.get(f"/api/v1/records/{record_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _snapshot(detail: dict[str, Any]) -> tuple[Any, ...]:
    """Pick the target's own digest, approval state and history."""
    approval = detail["approval"]
    return (
        detail["metadata"]["digest"],
        approval["state"],
        approval["history"],
    )


def test_published_erratum_is_reported_then_verified_then_rejected(
    client: TestClient,
    provider: PostgresStoreProvider,
    router_settings: Settings,
) -> None:
    """Ensure erratum decisions show on the target, never touching it."""
    target, [first, second] = _seed_target(provider, errata=2)
    before = _detail(client, target)
    [entry, _] = before["errata"]
    assert entry["id"] == first
    assert entry["kind"] == "published"
    assert entry["type"] == "technical"
    assert entry["section"] == "S0"
    assert entry["reported_by"] == "alice@example.com"
    assert entry["reported_date"] == "2024-04-01"
    assert "Old words." in entry["original_html"]
    assert "New words." in entry["corrected_html"]
    assert "Why it changed." in entry["notes_html"]
    assert entry["approval_state"] == "pending"
    assert entry["has_content"] is True
    assert before["errata_summary"] == {
        "total": 2,
        "verified": 0,
        "reported": 2,
        "rejected": 0,
        "changed": 0,
        "proposed": 0,
    }

    as_user(client, router_settings)
    assert decide(client, first, "accepted").status_code == 201
    assert decide(client, second, "rejected").status_code == 201

    after = _detail(client, target)
    states = {e["id"]: e["approval_state"] for e in after["errata"]}
    assert states == {first: "accepted", second: "rejected"}
    summary = after["errata_summary"]
    assert (summary["verified"], summary["rejected"]) == (1, 1)
    assert summary["reported"] == 0
    assert _snapshot(after) == _snapshot(before)
    assert after["approval"]["state"] == "pending"
    assert after["approval"]["history"] == []


def test_pushed_candidate_erratum_is_proposed(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure a pushed erratum candidate shows as a proposal."""
    target, _ = _seed_target(provider, errata=0)
    body = candidate(
        ERRATUM_C,
        content=erratum_text(ERRATUM_C),
        path="doc/decisions/errata/2024-04-09-proposal.md",
    )
    response = push(client, body)
    assert response.status_code == 201, response.text

    detail = _detail(client, target)

    [entry] = detail["errata"]
    assert entry["id"] == response.json()["record_id"]
    assert entry["kind"] == "candidate"
    assert entry["ref"] == "feature/catalog"
    assert entry["approval_state"] == "pending"
    summary = detail["errata_summary"]
    assert (summary["total"], summary["proposed"]) == (0, 1)


def test_erratum_page_has_content_and_resolved_target(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure an erratum page shows its content and its target."""
    target, [erratum] = _seed_target(provider)

    detail = _detail(client, erratum)

    assert detail["metadata"]["record_kind"] == "erratum"
    assert detail["erratum"]["type"] == "technical"
    assert "New words." in detail["erratum"]["corrected_html"]
    assert detail["erratum_for"] == {
        "uuid": str(TARGET),
        "id": target,
        "title": "Use a queue",
        "resolved": True,
    }
    assert all(
        link["link_type"] != "corrects" for link in detail["outbound_links"]
    )
    assert detail["errata"] == []


def test_decision_page_has_no_erratum_fields(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure a decision has no erratum content or target."""
    target, _ = _seed_target(provider, errata=0)

    detail = _detail(client, target)

    assert detail["erratum"] is None
    assert detail["erratum_for"] is None
    assert detail["errata"] == []
    assert detail["errata_summary"]["total"] == 0


def test_unresolved_erratum_target(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure an erratum for an unknown UUID reports it unresolved."""
    missing = uuid.uuid4()
    with provider.lock_registration("central") as store:
        erratum = seed(
            store,
            path="doc/decisions/errata/2024-04-01-x.md",
            content=erratum_text(ERRATUM_A, missing).encode(),
        )

    detail = _detail(client, str(erratum))

    assert detail["erratum_for"] == {
        "uuid": str(missing),
        "id": None,
        "title": None,
        "resolved": False,
    }


def test_erratum_belongs_to_the_closest_decision(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure same-project-first resolution decides an erratum's target."""
    platform, [erratum] = _seed_target(provider, project="platform")
    with provider.lock_registration("central") as store:
        payments = seed(
            store,
            project="payments",
            path=DECISION_PATH,
            content=adr(TARGET, title="Use a queue (payments)"),
        )

    assert [e["id"] for e in _detail(client, platform)["errata"]] == [erratum]
    assert _detail(client, str(payments))["errata"] == []


def _search(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    """Run a search and return its items."""
    response = client.get("/api/v1/records", params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_search_record_type_filter(
    client: TestClient,
    provider: PostgresStoreProvider,
    router_settings: Settings,
) -> None:
    """Ensure errata are hidden by default and selectable by type."""
    target, [first, second] = _seed_target(provider, errata=2)

    default = _search(client)
    errata = _search(client, record_type="erratum")
    both = _search(client, record_type="all")

    assert [item["id"] for item in default] == [target]
    assert default[0]["erratum_for_title"] is None
    assert {item["id"] for item in errata} == {first, second}
    assert {item["erratum_for_title"] for item in errata} == {"Use a queue"}
    assert {item["id"] for item in both} == {target, first, second}

    as_user(client, router_settings)
    assert decide(client, first, "accepted").status_code == 201
    needing = _search(client, record_type="erratum", needs_approval="true")
    assert [item["id"] for item in needing] == [second]
    assert {
        item["id"]
        for item in _search(client, record_type="all", needs_approval="true")
    } == {target, second}


def test_search_rejects_unknown_record_type(client: TestClient) -> None:
    """Ensure an unknown ``record_type`` is a 422."""
    response = client.get("/api/v1/records", params={"record_type": "x"})

    assert response.status_code == 422


@contextmanager
def _count_statements() -> Iterator[list[str]]:
    """
    Count every SQL statement sent by any engine.

    :returns: The list the statements are appended to.
    """
    statements: list[str] = []

    def _record(*args: Any) -> None:
        statements.append(args[2])

    event.listen(Engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(Engine, "before_cursor_execute", _record)


def _detail_statements(client: TestClient, record_id: str) -> int:
    """Count the statements of one detail request."""
    with _count_statements() as statements:
        _detail(client, record_id)
    return len(statements)


def test_detail_query_count_does_not_grow_with_errata(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure the detail request makes a constant number of queries."""
    one, _ = _seed_target(provider, errata=1, project="platform")
    with provider.lock_registration("central") as store:
        many = seed(
            store,
            project="payments",
            path=DECISION_PATH,
            content=adr(ERRATUM_B, title="Many errata"),
        )
        for number in range(5):
            own = uuid.uuid5(ERRATUM_B, str(number))
            seed(
                store,
                project="payments",
                path=f"doc/decisions/errata/2024-05-0{number + 1}-x.md",
                content=erratum_text(own, ERRATUM_B).encode(),
            )

        none = seed(
            store,
            project="payments",
            path="doc/decisions/2024-01-02-no-errata.md",
            content=adr(ERRATUM_C, title="No errata"),
        )

    assert len(_detail(client, str(many))["errata"]) == 5
    counts = [
        _detail_statements(client, record_id)
        for record_id in (str(none), one, str(many))
    ]
    # Errata add one decisions query in total, never one per erratum.
    assert counts[1] == counts[0] + 1
    assert counts[2] == counts[1]
