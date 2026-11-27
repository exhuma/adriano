"""
The ``approvable`` flag on list-style payloads.

Search rows, siblings, competing candidates and errata carry the same
``approvable`` value as ``approval.approvable`` on the row's own
detail page (:func:`app.services.approval_view.is_approvable`), so the
UI can show "Blocked" instead of "Pending approval" everywhere.

A file that is not valid UTF-8 keeps its authored UUID (and so its
identity) but cannot be decided. A file without a UUID is not a record
at all (it goes to the not-indexed list).
"""

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.storage.port import RecordState
from app.storage.postgres.store import PostgresStoreProvider
from tests.routers.conftest import adr, seed

ADR_UUID = uuid.UUID("a9900000-0000-4000-8000-000000000001")
TARGET = uuid.UUID("a9900000-0000-4000-8000-000000000002")
ERRATUM = uuid.UUID("a9900000-0000-4000-8000-000000000003")
PATH = "doc/decisions/2024-01-01-flags.md"


def _bad_encoding(content: bytes) -> bytes:
    """Make *content* invalid UTF-8 by Latin-1 encoding one ``é``."""
    assert "é".encode() in content
    return content.replace("é".encode(), b"\xe9")


def _detail(
    client: TestClient, adr_uuid: uuid.UUID, ref: str | None = None
) -> dict[str, Any]:
    """Read one record detail (a candidate when *ref* is given)."""
    params = {} if ref is None else {"ref": ref}
    response = client.get(f"/api/v1/records/{adr_uuid}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _seed_identity(provider: PostgresStoreProvider) -> None:
    """
    Seed one published row and two candidates of the same ADR.

    Ref ``feature-a`` is not valid UTF-8 (unapprovable), ``feature-b``
    is approvable.
    """
    with provider.lock_registration("central") as store:
        seed(store, path=PATH, content=adr(ADR_UUID))
        seed(
            store,
            path=PATH,
            ref="feature-a",
            kind=RecordState.CANDIDATE,
            content=_bad_encoding(adr(ADR_UUID, body="Café one.")),
        )
        seed(
            store,
            path=PATH,
            ref="feature-b",
            kind=RecordState.CANDIDATE,
            content=adr(ADR_UUID, body="Café two."),
        )


def test_siblings_and_competing_candidates_carry_approvable(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure siblings and competing candidates match their own detail."""
    _seed_identity(provider)

    detail = _detail(client, ADR_UUID)

    siblings = {s["ref"]: s["approvable"] for s in detail["siblings"]}
    competing = {
        c["ref"]: c["approvable"]
        for c in detail["approval"]["competing_candidates"]
    }
    expected = {"feature-a": False, "feature-b": True}
    assert siblings == expected
    assert competing == expected
    assert {s["id"] for s in detail["siblings"]} == {str(ADR_UUID)}
    for ref, flag in expected.items():
        own = _detail(client, ADR_UUID, ref)
        assert own["approval"]["approvable"] is flag


def test_search_rows_carry_approvable(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure search rows flag unapprovable content (bad UTF-8)."""
    _seed_identity(provider)

    response = client.get("/api/v1/records", params={"page_size": 50})

    assert response.status_code == 200
    flags = {
        (i["id"], i["ref"]): i["approvable"] for i in response.json()["items"]
    }
    assert flags == {
        (str(ADR_UUID), "local"): True,
        (str(ADR_UUID), "feature-a"): False,
        (str(ADR_UUID), "feature-b"): True,
    }


def test_errata_carry_approvable(
    client: TestClient, provider: PostgresStoreProvider
) -> None:
    """Ensure an erratum that is not valid UTF-8 is flagged unapprovable."""
    erratum = (
        f"---\nuuid: {ERRATUM}\nerratum-for: {TARGET}\ntype: editorial\n"
        "section: Context\ndate: 2024-04-01\n---\n"
        "## Original text\n\nOld words.\n\n"
        "## Corrected text\n\nNew café.\n"
    ).encode()
    with provider.lock_registration("central") as store:
        target = seed(store, path=PATH, content=adr(TARGET))
        erratum_id = seed(
            store,
            path="doc/decisions/errata/2024-04-01-fix.md",
            content=_bad_encoding(erratum),
        )

    detail = _detail(client, target)

    [item] = detail["errata"]
    assert item["id"] == str(erratum_id)
    assert item["approvable"] is False
    assert _detail(client, erratum_id)["approval"]["approvable"] is False
