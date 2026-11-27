"""
Find the record row a reader or reviewer addresses.

A record is addressed by its ADR UUID, optionally with a ref: the ref
picks a candidate, no ref picks the published row. An ADR that is only
proposed (candidates, no published row) is shown through its most
recently updated candidate.

Public API: :func:`find_record`.
"""

import uuid

from app.storage.port import CatalogStore, StoredRecord


def find_record(
    store: CatalogStore, adr_uuid: uuid.UUID, ref: str | None = None
) -> StoredRecord | None:
    """
    Find the row of an ADR to show or decide.

    :param store: Store of the caller's unit of work.
    :param adr_uuid: The ADR's UUID.
    :param ref: A candidate's ref; ``None`` for the published row.
    :returns: With *ref*: the candidate at *ref*, else the published row
        if it was read from *ref*. Without: the published row, else the
        most recently updated candidate. ``None`` if nothing matches.
    """
    if ref is not None:
        candidate = store.get_candidate(adr_uuid, ref)
        if candidate is not None:
            return candidate
        published = store.get_published(adr_uuid)
        return published if published and published.ref == ref else None
    published = store.get_published(adr_uuid)
    if published is not None:
        return published
    rows = store.list_records(adr_uuid)
    return max(rows, key=lambda row: (row.updated_at, row.ref), default=None)
