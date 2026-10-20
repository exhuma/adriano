"""Tests for ``GET /api/v1/records/{id}`` (the detail page)."""

import uuid

from fastapi.testclient import TestClient

from app.storage.port import RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.conftest import adr, seed

U1 = uuid.UUID("0b0c2f4e-1a2b-4c3d-8e9f-001122334455")
U2 = uuid.UUID("1b0c2f4e-1a2b-4c3d-8e9f-001122334455")
U3 = uuid.UUID("2b0c2f4e-1a2b-4c3d-8e9f-001122334455")
U4 = uuid.UUID("3b0c2f4e-1a2b-4c3d-8e9f-001122334455")
U5 = uuid.UUID("4b0c2f4e-1a2b-4c3d-8e9f-001122334455")


def test_record_not_found_is_404(client: TestClient) -> None:
    """Ensure an unknown record id returns 404 via the domain handler."""
    response = client.get(f"/api/v1/records/{uuid.uuid4()}")

    assert response.status_code == 404


def test_legacy_fields_and_a_missing_link_target(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure legacy sign-off/deprecates show and a broken link is flagged."""
    with provider.lock_registration("central") as store:
        record_id = seed(
            store,
            content=adr(
                U1,
                title="Legacy decision",
                extra=(
                    f"deprecates: {U2}\n"
                    "signed-off-by: [a@example.com, b@example.com]\n"
                ),
            ),
        )

    response = client.get(f"/api/v1/records/{record_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["legacy_signoff_unverified"] == [
        "a@example.com",
        "b@example.com",
    ]
    codes = {issue["code"] for issue in body["issues"]}
    assert "legacy_alias" in codes
    assert "legacy_signoff" in codes
    assert "missing_target" in codes
    [outbound] = body["outbound_links"]
    assert outbound["link_type"] == "obsoletes"
    assert outbound["target_uuid"] == str(U2)
    assert outbound["target_id"] is None
    assert outbound["target_title"] is None
    assert body["approval"]["state"] == "pending"
    assert body["approval"]["needs_approval"] is True
    assert body["approval"]["policy"]["id"] == "global"
    assert body["approval"]["history"] == []


def test_erratum_is_listed_on_the_corrected_record(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure an erratum shows up as errata on the decision it corrects."""
    with provider.lock_registration("central") as store:
        decision_id = seed(
            store,
            path="doc/decisions/2024-01-01-decision.md",
            content=adr(U3, title="Decision with an erratum"),
        )
        seed(
            store,
            path="doc/decisions/2024-01-02-erratum.md",
            content=adr(
                U5,
                title="Correction",
                body="## Corrected text\n\nFixing a typo.",
                extra=f"erratum-for: {U3}\ntype: editorial\n",
            ),
        )

    response = client.get(f"/api/v1/records/{decision_id}")

    assert response.status_code == 200
    body = response.json()
    [erratum] = body["errata"]
    assert erratum["title"] == "Correction"
    assert erratum["kind"] == "published"
    assert erratum["type"] == "editorial"
    assert "Fixing a typo." in erratum["corrected_html"]
    assert erratum["approval_state"] == "pending"
    assert body["errata_summary"]["reported"] == 1


def test_inbound_obsoleted_by_and_derived_status(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure the obsoleted record shows the replacement and its status."""
    with provider.lock_registration("central") as store:
        old_id = seed(
            store,
            path="doc/decisions/2024-01-01-old.md",
            content=adr(U4, title="Old decision"),
        )
        new_id = seed(
            store,
            path="doc/decisions/2024-01-02-new.md",
            content=adr(
                uuid.uuid4(),
                title="New decision",
                extra=f"obsoletes: [{U4}]\n",
            ),
        )

    response = client.get(f"/api/v1/records/{old_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "obsoleted"
    [inbound] = body["inbound_links"]
    assert inbound["link_type"] == "obsoleted_by"
    assert inbound["source_id"] == str(new_id)
    assert inbound["source_title"] == "New decision"


def test_an_invalid_record_does_not_affect_others(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure a record with bad frontmatter is isolated, others unaffected."""
    with provider.lock_registration("central") as store:
        valid_id = seed(
            store,
            path="doc/decisions/2024-01-01-valid.md",
            content=adr(uuid.uuid4(), title="Still fine"),
        )
        broken_id = seed(
            store,
            path="doc/decisions/2024-01-02-broken.md",
            content=b"not frontmatter at all",
        )

    valid_response = client.get(f"/api/v1/records/{valid_id}")
    broken_response = client.get(f"/api/v1/records/{broken_id}")

    assert valid_response.status_code == 200
    assert valid_response.json()["metadata"]["title"] == "Still fine"
    assert broken_response.status_code == 200
    broken_body = broken_response.json()
    assert broken_body["metadata"]["adr_uuid"] is None
    codes = {issue["code"] for issue in broken_body["issues"]}
    assert "missing_frontmatter" in codes
    assert broken_body["approval"]["state"] == "pending"


def test_candidate_detail_uses_identity_siblings_for_relationships(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure a candidate's own identity row participates in its view."""
    with provider.lock_registration("central") as store:
        candidate_id = seed(
            store,
            ref="feature",
            kind=RecordState.CANDIDATE,
            content=adr(uuid.uuid4(), title="Candidate only"),
        )

    response = client.get(f"/api/v1/records/{candidate_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["kind"] == "candidate"
    assert body["siblings"] == []


def test_detail_siblings_exclude_the_record_itself(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure siblings list the other revisions, never the record itself."""
    adr_uuid = uuid.uuid4()
    with provider.lock_registration("central") as store:
        published_id = seed(store, content=adr(adr_uuid, title="Same"))
        candidate_id = seed(
            store,
            ref="feature",
            kind=RecordState.CANDIDATE,
            content=adr(adr_uuid, title="Same, edited"),
        )

    response = client.get(f"/api/v1/records/{published_id}")

    [sibling] = response.json()["siblings"]
    assert sibling["id"] == str(candidate_id)
    assert sibling["kind"] == "candidate"
