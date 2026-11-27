"""
Apply a registration's poll plan: the UUID holder rule and reconciliation.

An ADR is identified by its UUID across every registration and project
(``record.adr_uuid``); where its file lives is an attribute. Applying a
:class:`~app.services.poll_plan.PollPlan` therefore decides, per fetched
document carrying UUID *U* at location *L*:

- nothing holds *U* -> insert the published row;
- the row of *U* lives at *L* -> update it;
- the row of *U* lives elsewhere but its file **released** *U* (see
  below) -> **move**: update the row in place with the new location,
  keeping ``first_seen_at``, ``previous_digest`` and the approvals
  (decisions are keyed by UUID and digest);
- otherwise the holder keeps *U* and the document goes to the
  not-indexed list as ``duplicate_uuid`` with ``holder_uuid`` = *U*.

A holder's file **releases** its UUID only when it is known not to
carry it any more (:meth:`PollRun.releases`): its location is gone from
a complete listing (also: its project left a complete project listing,
or its registration was removed from the configuration), or it was
read in this run and carries another UUID or none. A holder whose
registration was not polled in this run, or whose file could not be
read, keeps the UUID.

Documents are applied in configuration order of their registration,
then by project and path, so when two new files claim one UUID in the
same run the first of them wins. :class:`PollRun` carries what every
registration of one run (``poll_all``) found, so a file moved from one
registration to another in the same run is a move, not a delete and an
insert: the removal is skipped when a later registration of the run
claims the UUID, and that registration moves the row.

Deletion: a stored row whose file released its UUID is deleted unless
it was moved; deletes are guarded by the expected location, so a row
another registration moved in the meantime survives.

Not-indexed list (poll entries, keyed by location and ref): a document
without a valid UUID, a losing duplicate or an unreadable document is
written (or rewritten, keeping ``first_seen_at``); an entry is cleared
when its location gets indexed, when it is gone from a complete
listing, or when its registration is removed from the configuration
(:func:`clear_removed_sources`, which clears push entries too). A poll
never clears a push entry for
not being listed (a pushed branch is not in the listing); it clears
the push entries at a file location where it now indexes a document,
whatever their ref or reason (an invalid or mismatched push, or a
duplicate, that the author fixed and merged). Nothing else removes an
entry.

Public API: :class:`PollRun`, :func:`apply_plan`,
:func:`clear_removed_sources`.
"""

import uuid
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field

from app.domain.issues import Issue, IssueCode, error
from app.services.ingest import (
    PreparedDocument,
    ingest_document,
    not_indexed_entry,
    queue_document,
)
from app.services.poll_plan import PollPlan
from app.storage.port import (
    CatalogStore,
    ChangeTokenEntry,
    IntakeKind,
    Location,
    NotIndexedKey,
    NotIndexedWrite,
    RecordState,
)


@dataclass(slots=True)
class PollRun:
    """
    What every registration of one poll run found, for the holder rule.

    :param configured: Ids of the configured registrations; a holder in
        any other registration has released its UUIDs.
    :param vanished: Locations gone from a complete listing.
    :param carried: UUID each successfully read location carries now
        (``None``: no valid UUID).
    :param claims: Configuration positions of the registrations whose
        fetched documents claim each UUID.
    """

    configured: frozenset[str]
    vanished: set[Location] = field(default_factory=set)
    carried: dict[Location, uuid.UUID | None] = field(default_factory=dict)
    claims: dict[uuid.UUID, list[int]] = field(default_factory=dict)

    def add(self, position: int, plan: PollPlan) -> None:
        """
        Record what one registration's collected plan found.

        :param position: The registration's configuration position.
        :param plan: Its collected plan.
        """
        self.vanished.update(entry.location for entry in plan.vanished)
        for prepared in plan.prepared:
            record = prepared.record
            carried = None if record is None else record.adr_uuid
            self.carried[_location(prepared)] = carried
            if carried is not None:
                self.claims.setdefault(carried, []).append(position)

    def releases(self, holder: ChangeTokenEntry) -> bool:
        """
        Tell whether a holder's file no longer carries its UUID.

        :param holder: The stored published row (UUID and location).
        :returns: ``True`` when the UUID is free to move or be removed.
        """
        location = holder.location
        if location.source_id not in self.configured:
            return True
        if location in self.vanished:
            return True
        return (
            location in self.carried
            and self.carried[location] != holder.adr_uuid
        )

    def claimed_after(self, adr_uuid: uuid.UUID, position: int) -> bool:
        """
        Tell whether a later registration of the run claims a UUID.

        :param adr_uuid: The UUID.
        :param position: Configuration position of the current one.
        :returns: ``True`` if a registration after *position* fetched a
            document with this UUID.
        """
        return any(p > position for p in self.claims.get(adr_uuid, []))


def _location(prepared: PreparedDocument) -> Location:
    """
    Read the location of a prepared document.

    :param prepared: The document.
    :returns: ``(source_id, project, path)``.
    """
    return prepared.document.key.location


def _duplicate(holder: ChangeTokenEntry) -> tuple[Issue, ...]:
    """
    Describe a losing duplicate.

    :param holder: Where the UUID is held.
    :returns: The ``duplicate_uuid`` reason.
    """
    return (
        error(
            IssueCode.DUPLICATE_UUID,
            f"UUID {holder.adr_uuid} is already used by {holder.location}; "
            "give this file its own UUID",
        ),
    )


@dataclass(slots=True)
class _Apply:
    """
    State of applying one registration's plan.

    :param store: The locked store.
    :param plan: The plan.
    :param run: Knowledge of the whole run.
    :param holders: Published row per claimed UUID, kept current.
    :param written: Not-indexed keys written by this apply.
    :param indexed: File location of every document indexed.
    """

    store: CatalogStore
    plan: PollPlan
    run: PollRun
    holders: dict[uuid.UUID, ChangeTokenEntry]
    written: set[NotIndexedKey] = field(default_factory=set)
    indexed: list[Location] = field(default_factory=list)

    def index(self, prepared: PreparedDocument) -> None:
        """
        Index one fetched document, or list it as not indexed.

        :param prepared: The document.
        """
        record = prepared.record
        if record is None:
            self.queue(prepared, not_indexed_entry(prepared, IntakeKind.POLL))
            return
        holder = self.holders.get(record.adr_uuid)
        location = _location(prepared)
        if holder is not None and holder.location != location:
            if not self.run.releases(holder):
                entry = not_indexed_entry(
                    prepared,
                    IntakeKind.POLL,
                    reasons=_duplicate(holder),
                    holder_uuid=record.adr_uuid,
                )
                self.queue(prepared, entry)
                return
        self.write(prepared)

    def write(self, prepared: PreparedDocument) -> None:
        """
        Upsert the published row of a document allowed to hold its UUID.

        :param prepared: The document (with a row).
        """
        result = ingest_document(self.store, prepared, RecordState.PUBLISHED)
        record = prepared.record
        assert record is not None
        self.indexed.append(_location(prepared))
        self.holders[record.adr_uuid] = ChangeTokenEntry(
            adr_uuid=record.adr_uuid,
            source_id=record.source_id,
            project=record.project,
            path=record.path,
            change_token=record.change_token,
            digest=record.digest,
        )
        counts = self.plan.counts
        if result.created:
            counts.created += 1
        elif result.moved:
            counts.moved += 1
        elif result.digest_changed:
            counts.updated += 1
        else:
            counts.same_content += 1

    def queue(self, prepared: PreparedDocument, entry: NotIndexedWrite) -> None:
        """
        Write a not-indexed entry for a fetched document.

        :param prepared: The document.
        :param entry: Its entry.
        """
        queue_document(self.store, prepared, entry)
        self.written.add(entry.key)
        self.plan.counts.not_indexed += 1

    def released_rows(self) -> list[ChangeTokenEntry]:
        """
        List this registration's stored rows whose file released them.

        :returns: Vanished rows plus rows whose file was read and now
            carries another UUID or none.
        """
        rows = list(self.plan.vanished)
        for prepared in self.plan.prepared:
            document = prepared.document
            stored = self.plan.stored.own.get(document.project, {})
            entry = stored.get(document.path)
            if entry is not None and self.run.releases(entry):
                rows.append(entry)
        return rows


def _stale_keys(
    plan: PollPlan, written: Collection[NotIndexedKey]
) -> set[NotIndexedKey]:
    """
    List the poll entries of the not-indexed list that no longer apply.

    :param plan: The plan.
    :param written: Keys rewritten by this apply (kept).
    :returns: Keys of vanished entries and of entries at every fetched
        or unreadable location that were not rewritten.
    """
    touched = {_location(p) for p in plan.prepared}
    touched |= {entry.key.location for entry in plan.unreadable}
    stale = {entry.key for entry in plan.vanished_queue}
    stale |= {
        entry.key
        for paths in plan.stored.queued.values()
        for entries in paths.values()
        for entry in entries
        if entry.key.location in touched
    }
    return stale - set(written)


def apply_plan(
    store: CatalogStore, plan: PollPlan, run: PollRun, position: int
) -> None:
    """
    Write one registration's plan inside its locked unit of work.

    :param store: Store locked for the registration.
    :param plan: The collected plan.
    :param run: Knowledge of the whole poll run (see :class:`PollRun`).
    :param position: The registration's configuration position.
    """
    store.lock_published()
    claimed = {p.record.adr_uuid for p in plan.prepared if p.record}
    holders = {e.adr_uuid: e for e in store.list_published_entries(claimed)}
    state = _Apply(store=store, plan=plan, run=run, holders=holders)
    for prepared in sorted(plan.prepared, key=_location):
        state.index(prepared)
    for entry in plan.unreadable:
        store.put_not_indexed(entry)
        state.written.add(entry.key)
        plan.counts.not_indexed += 1
    for entry, token in plan.refresh:
        if store.set_change_token(entry, token):
            plan.counts.tokens_refreshed += 1
    removed = [
        entry
        for entry in state.released_rows()
        if not run.claimed_after(entry.adr_uuid, position)
    ]
    plan.counts.deleted = store.delete_published(removed)
    store.delete_not_indexed(_stale_keys(plan, state.written))
    store.clear_pushed_at(state.indexed)


def clear_removed_sources(
    store: CatalogStore, configured: Iterable[str]
) -> int:
    """
    Clear the entries of registrations no longer configured.

    Both origins go: no push can arrive for an unconfigured
    registration, so a push entry could never clear otherwise.

    :param store: Store of the caller's unit of work.
    :param configured: Ids of the configured registrations.
    :returns: Number of cleared entries.
    """
    known = set(configured)
    stale = [
        entry.key
        for entry in store.list_not_indexed()
        if entry.key.source_id not in known
    ]
    return store.delete_not_indexed(stale)
