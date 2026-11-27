"""
Revisions and the published and candidate records.

Part of the :class:`app.storage.port.CatalogStore` protocol, split by
concern to keep modules small. Import :class:`RecordStore` only to compose
the store; services depend on :mod:`app.storage.port`.

Public API: :class:`RecordStore`.
"""

import uuid
from collections.abc import Collection
from typing import Protocol

from app.domain.relationships import RecordSummary
from app.storage.values import (
    ChangeTokenEntry,
    ErratumRow,
    RecordWrite,
    Revision,
    StoredRecord,
    UpsertResult,
)


class RecordStore(Protocol):
    """Revisions and the published and candidate records."""

    def put_revision(self, digest: str, content: str) -> bool:
        """
        Store a snapshot unless it exists (snapshots are immutable).

        :param digest: Digest string.
        :param content: Canonical text content.
        :returns: ``True`` if it was newly stored.
        """
        ...

    def get_revision(self, digest: str) -> Revision | None:
        """
        Fetch a snapshot.

        :param digest: Digest string.
        :returns: The snapshot, or ``None``.
        """
        ...

    def lock_published(self) -> None:
        """
        Take the catalog-wide lock for writing published rows.

        Held until the unit of work ends. A UUID is unique across all
        registrations, so a poll that decides who holds a UUID (and
        moves rows between registrations) must not interleave with
        another registration's poll; candidates and pushes do not need
        it.
        """
        ...

    def upsert_published(self, record: RecordWrite) -> UpsertResult:
        """
        Insert or replace the published row of an ADR.

        Keyed by ``adr_uuid`` alone: an existing row is updated in place,
        including its location (a move keeps ``first_seen_at``, digest
        history and approvals). Deciding *whether* a file may hold the
        UUID is the caller's job (the holder rule of
        :mod:`app.services.poll_apply`).

        :param record: Row content.
        :returns: The outcome.
        """
        ...

    def upsert_candidate(self, record: RecordWrite) -> UpsertResult:
        """
        Insert or replace a candidate row.

        Keyed by ``(adr_uuid, ref)``.

        :param record: Row content.
        :returns: The outcome.
        """
        ...

    def create_candidate(self, record: RecordWrite) -> UpsertResult:
        """
        Insert a candidate row only if its key is free.

        :param record: Row content.
        :returns: The outcome (always ``created``).
        :raises app.errors.CandidateExistsError: If the candidate
            ``(adr_uuid, ref)`` exists.
        """
        ...

    def get_published(self, adr_uuid: uuid.UUID) -> StoredRecord | None:
        """
        Fetch the published row of an ADR.

        :param adr_uuid: The ADR's UUID.
        :returns: The row, or ``None``.
        """
        ...

    def get_candidate(
        self, adr_uuid: uuid.UUID, ref: str
    ) -> StoredRecord | None:
        """
        Fetch one candidate row.

        :param adr_uuid: The ADR's UUID.
        :param ref: The candidate's ref.
        :returns: The row, or ``None``.
        """
        ...

    def list_records(self, adr_uuid: uuid.UUID) -> list[StoredRecord]:
        """
        List every row (published and candidates) of an ADR.

        :param adr_uuid: The ADR's UUID.
        :returns: Rows, published first, then candidates by ref.
        """
        ...

    def list_change_tokens(
        self, source_id: str, project: str | None = None
    ) -> list[ChangeTokenEntry]:
        """
        List the published files of a registration with their tokens.

        Listings know paths before content is fetched, so change
        detection looks up by location; the row it maps to is keyed by
        the UUID in :attr:`ChangeTokenEntry.adr_uuid`.

        :param source_id: Registration id.
        :param project: Restrict to one project; ``None`` means all.
        :returns: Entries ordered by project and path.
        """
        ...

    def list_published_entries(
        self, uuids: Collection[uuid.UUID]
    ) -> list[ChangeTokenEntry]:
        """
        List where the published rows of some UUIDs live (any source).

        :param uuids: ADR UUIDs.
        :returns: One entry per UUID that has a published row.
        """
        ...

    def set_change_token(
        self, entry: ChangeTokenEntry, change_token: str | None
    ) -> bool:
        """
        Rewrite the change token of an unchanged published file.

        Only touches the row if it still lives at the entry's location.

        :param entry: The stored entry (UUID and location).
        :param change_token: The new token.
        :returns: ``True`` if a row was updated.
        """
        ...

    def delete_published(self, entries: Collection[ChangeTokenEntry]) -> int:
        """
        Delete published rows (reconciliation). Candidates are kept.

        A row is deleted only if it still lives at the entry's location,
        so a row another registration moved in the meantime survives.

        :param entries: UUIDs with their expected locations.
        :returns: Number of deleted rows.
        """
        ...

    def list_relationship_candidates(
        self, self_uuid: uuid.UUID, link_targets: Collection[uuid.UUID]
    ) -> list[RecordSummary]:
        """
        List published rows that can affect one record's relationships.

        See
        :func:`app.storage.postgres.records.list_relationship_candidates`
        for exactly which rows this returns.

        :param self_uuid: The viewed record's own UUID.
        :param link_targets: UUIDs the viewed record's own ``updates``,
            ``obsoletes`` and ``corrects`` links target.
        :returns: One summary per matching published ADR.
        """
        ...

    def list_errata_for(self, target_uuid: uuid.UUID) -> list[ErratumRow]:
        """
        List the erratum rows whose ``corrects`` link is *target_uuid*.

        Includes published rows and candidates (proposed errata), from
        every registration and project. Decisions are never returned.

        :param target_uuid: UUID of the corrected decision.
        :returns: Published rows first, then by source, project, path,
            ref and UUID.
        """
        ...

    def published_titles(
        self, uuids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """
        Look up the titles of the published rows of some UUIDs.

        One query for a whole set (link targets of a detail page,
        erratum targets of a search page).

        :param uuids: ADR UUIDs.
        :returns: Title by UUID, for UUIDs with a published row.
        """
        ...
