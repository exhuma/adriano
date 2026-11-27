"""
Tests for the UUID-addressed record routes.

An ADR is ``/records/{uuid}``; a candidate is
``/records/{uuid}/candidates/{ref}`` with a slash-containing ref; the
diff and decision routes take the ref as a query parameter. Search
returns one hit per ADR.
"""

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.storage.port import RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.approval.support import (
    adr_text,
    as_user,
    candidate,
    push,
)
from tests.routers.conftest import adr, seed

ADR = uuid.UUID("0b0c2f4e-2222-4a4a-9a9a-000000000001")
PATH = "doc/decisions/2024-03-01-routes.md"


def _items(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    """List the search hits."""
    response = client.get("/api/v1/records", params={"page_size": 50, **params})
    assert response.status_code == 200
    return response.json()["items"]


def test_candidate_with_a_slash_ref_has_its_own_route(
    client: TestClient,
) -> None:
    """Ensure refs containing slashes are addressed after /candidates/."""
    push(client, candidate(ADR, ref="feature/deep/branch"))

    response = client.get(
        f"/api/v1/records/{ADR}/candidates/feature/deep/branch"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["adr_uuid"] == str(ADR)
    assert "id" not in body["metadata"]
    assert body["provenance"]["ref"] == "feature/deep/branch"
    assert body["metadata"]["kind"] == "candidate"


def test_an_unknown_ref_is_404(client: TestClient) -> None:
    """Ensure a ref without a row is a 404 naming the ref."""
    push(client, candidate(ADR, ref="feature/a"))

    response = client.get(f"/api/v1/records/{ADR}/candidates/feature/zzz")

    assert response.status_code == 404
    assert response.json()["code"] == "record_not_found"
    assert "feature/zzz" in response.json()["detail"]


def test_the_plain_route_prefers_the_published_row(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure /records/{uuid} is the published row, not a candidate."""
    with provider.lock_registration("central") as store:
        seed(store, path=PATH, content=adr(ADR, title="Published"))
    push(client, candidate(ADR, content=adr_text(ADR, title="Proposed")))

    plain = client.get(f"/api/v1/records/{ADR}").json()
    proposed = client.get(f"/api/v1/records/{ADR}/candidates/feature/catalog")

    assert plain["metadata"]["kind"] == "published"
    assert plain["metadata"]["title"] == "Published"
    assert [(s["adr_uuid"], s["ref"]) for s in plain["siblings"]] == [
        (str(ADR), "feature/catalog")
    ]
    assert proposed.json()["metadata"]["title"] == "Proposed"


def test_the_plain_route_shows_the_newest_candidate_without_a_row(
    client: TestClient,
) -> None:
    """Ensure an unpublished ADR shows its most recent candidate."""
    push(client, candidate(ADR, ref="feature/old"))
    push(
        client,
        candidate(
            ADR,
            ref="feature/new",
            content=adr_text(ADR, body="Newer words."),
        ),
    )

    body = client.get(f"/api/v1/records/{ADR}").json()

    assert body["provenance"]["ref"] == "feature/new"


def test_diff_takes_the_ref_as_a_query_parameter(
    client: TestClient,
) -> None:
    """Ensure a slash ref reaches the diff route."""
    push(client, candidate(ADR, ref="feature/x/y"))

    diff = client.get(
        f"/api/v1/records/{ADR}/diff", params={"ref": "feature/x/y"}
    )
    missing = client.get(
        f"/api/v1/records/{ADR}/diff", params={"ref": "feature/none"}
    )

    assert diff.status_code == 200
    assert missing.status_code == 404


def test_a_decision_on_a_candidate_ref_is_recorded(
    client: TestClient,
) -> None:
    """Ensure POST /decisions?ref= decides that candidate's content."""
    push(client, candidate(ADR, ref="feature/x/y"))
    as_user(client)

    response = client.post(
        f"/api/v1/records/{ADR}/decisions",
        params={"ref": "feature/x/y"},
        json={"action": "accepted"},
    )

    assert response.status_code == 201
    assert response.json()["provenance"]["ref"] == "feature/x/y"


def test_cross_references_identify_rows_by_uuid_and_ref(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure siblings, competing candidates and divergence use UUID+ref."""
    with provider.lock_registration("central") as store:
        seed(store, path=PATH, content=adr(ADR, title="Published"))
    push(client, candidate(ADR, ref="feature/a"))
    push(
        client,
        candidate(
            ADR, ref="feature/b", content=adr_text(ADR, body="Other words.")
        ),
    )

    body = client.get(f"/api/v1/records/{ADR}/candidates/feature/a").json()

    for sibling in body["siblings"]:
        assert set(sibling) >= {"adr_uuid", "ref", "kind"}
        assert "id" not in sibling
    [competing] = body["approval"]["competing_candidates"]
    assert (competing["adr_uuid"], competing["ref"]) == (str(ADR), "feature/b")
    assert body["approval"]["divergence"]["other_rows"] == [
        {"adr_uuid": str(ADR), "ref": "local"}
    ]


def test_search_has_one_hit_per_adr(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure candidates do not add hits next to the published row."""
    other = uuid.UUID("0b0c2f4e-2222-4a4a-9a9a-000000000002")
    with provider.lock_registration("central") as store:
        seed(store, path=PATH, content=adr(ADR, title="Published"))
    push(client, candidate(ADR, ref="feature/a"))
    push(client, candidate(ADR, ref="feature/b"))
    push(client, candidate(other, ref="feature/old", path=None))
    push(
        client,
        candidate(
            other,
            ref="feature/new",
            path=None,
            content=adr_text(other, body="Newer."),
        ),
    )

    hits = {(i["adr_uuid"], i["ref"], i["kind"]) for i in _items(client)}

    assert hits == {
        (str(ADR), "local", "published"),
        (str(other), "feature/new", "candidate"),
    }
    assert client.get("/api/v1/records").json()["total"] == 2


def test_search_by_state_picks_the_row_kind(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure state filters keep one row per ADR as well."""
    with provider.lock_registration("central") as store:
        seed(store, path=PATH, content=adr(ADR, title="Published"))
        seed(
            store,
            path=PATH,
            ref="feature/a",
            kind=RecordState.CANDIDATE,
            content=adr(ADR, body="Candidate."),
        )
    push(client, candidate(ADR, ref="feature/b"))

    published = _items(client, state="published")
    candidates = _items(client, state="candidate")

    assert [(i["ref"], i["kind"]) for i in published] == [
        ("local", "published")
    ]
    assert [i["kind"] for i in candidates] == ["candidate"]
