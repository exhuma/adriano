"""
Route tests for malformed erratum relationships.

Covers an erratum that targets itself (also as stored by earlier
versions, with extra ``updates`` links), and an erratum of an erratum.
Read routes must stay total: content problems become issues, never
HTTP 500.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.conftest import adr, seed

DECISION = uuid.UUID("5b0c2f4e-1a2b-4c3d-8e9f-001122334455")
FIRST = uuid.UUID("6b0c2f4e-1a2b-4c3d-8e9f-001122334455")
SECOND = uuid.UUID("7b0c2f4e-1a2b-4c3d-8e9f-001122334455")


def erratum(
    adr_uuid: uuid.UUID, target: uuid.UUID, *, title: str, extra: str = ""
) -> bytes:
    """
    Render a small erratum document.

    :param adr_uuid: The erratum's own UUID.
    :param target: Its ``erratum-for`` UUID.
    :param title: Title.
    :param extra: Extra raw frontmatter lines.
    :returns: The document bytes.
    """
    return (
        f"---\nuuid: {adr_uuid}\ntitle: {title}\nerratum-for: {target}\n"
        f"type: editorial\n{extra}---\n## Corrected text\n\nFixed.\n"
    ).encode()


def _codes(body: dict[str, object]) -> set[str]:
    """
    Collect the issue codes of a detail response body.

    :param body: Parsed JSON body.
    :returns: The codes.
    """
    issues = body["issues"]
    assert isinstance(issues, list)
    return {issue["code"] for issue in issues}


@pytest.mark.parametrize("record_type", ["erratum", "all"])
def test_search_survives_a_legacy_self_targeting_erratum(
    client: TestClient,
    provider: PostgresStoreProvider,
    clean_engine: Engine,
    record_type: str,
) -> None:
    """Ensure a stored self-targeting erratum with updates does not 500."""
    with provider.lock_registration("central") as store:
        seed(
            store,
            path="doc/decisions/2024-01-01-decision.md",
            content=adr(DECISION, title="A decision"),
        )
        erratum_id = seed(
            store,
            path="doc/decisions/errata/2024-01-02-self.md",
            content=erratum(FIRST, FIRST, title="Self erratum"),
        )
    legacy = {
        "updates": [str(DECISION)],
        "obsoletes": [],
        "corrects": str(FIRST),
    }
    with clean_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE record SET links = CAST(:links AS jsonb) WHERE id = :id"
            ),
            {"links": json.dumps(legacy), "id": erratum_id},
        )

    response = client.get(
        "/api/v1/records", params={"record_type": record_type}
    )

    assert response.status_code == 200
    [item] = [
        hit for hit in response.json()["items"] if hit["id"] == str(erratum_id)
    ]
    assert item["erratum_for_title"] is None


@pytest.mark.parametrize("record_type", ["erratum", "all"])
def test_search_with_a_self_targeting_erratum_with_updates(
    client: TestClient, provider: PostgresStoreProvider, record_type: str
) -> None:
    """Ensure a newly ingested self-targeting erratum is searchable."""
    with provider.lock_registration("central") as store:
        seed(
            store,
            path="doc/decisions/2024-01-01-decision.md",
            content=adr(DECISION, title="A decision"),
        )
        erratum_id = seed(
            store,
            path="doc/decisions/errata/2024-01-02-self.md",
            content=erratum(
                FIRST,
                FIRST,
                title="Self erratum",
                extra=f"updates: [{DECISION}]\n",
            ),
        )

    response = client.get(
        "/api/v1/records", params={"record_type": record_type}
    )
    detail = client.get(f"/api/v1/records/{erratum_id}")

    assert response.status_code == 200
    assert str(erratum_id) in {hit["id"] for hit in response.json()["items"]}
    assert detail.status_code == 200
    body = detail.json()
    codes = _codes(body)
    assert "erratum_targets_itself" in codes
    assert "erratum_relationship_ignored" in codes
    assert body["outbound_links"] == []
    assert body["erratum_for"] is None


def test_erratum_of_an_erratum(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure an erratum lists no errata and flags an erratum target."""
    with provider.lock_registration("central") as store:
        seed(
            store,
            path="doc/decisions/2024-01-01-decision.md",
            content=adr(DECISION, title="A decision"),
        )
        first_id = seed(
            store,
            path="doc/decisions/errata/2024-01-02-first.md",
            content=erratum(FIRST, DECISION, title="First erratum"),
        )
        second_id = seed(
            store,
            path="doc/decisions/errata/2024-01-03-second.md",
            content=erratum(SECOND, FIRST, title="Erratum of an erratum"),
        )

    first = client.get(f"/api/v1/records/{first_id}").json()
    second = client.get(f"/api/v1/records/{second_id}").json()
    search = client.get("/api/v1/records", params={"record_type": "erratum"})

    assert first["errata"] == []
    assert first["errata_summary"]["total"] == 0
    assert first["errata_summary"]["proposed"] == 0
    assert "erratum_target_is_erratum" not in _codes(first)
    assert second["erratum_for"]["resolved"] is True
    assert second["erratum_for"]["id"] == str(first_id)
    [issue] = [
        issue
        for issue in second["issues"]
        if issue["code"] == "erratum_target_is_erratum"
    ]
    assert issue["severity"] == "warning"
    assert search.status_code == 200
    titles = {
        hit["title"]: hit["erratum_for_title"] for hit in search.json()["items"]
    }
    assert titles == {
        "First erratum": "A decision",
        "Erratum of an erratum": "First erratum",
    }
