"""
Unified diff between stored snapshots (``GET /api/v1/records/{id}/diff``).

The diff compares the exact canonical snapshots in the ``revision``
store (never Git history). Defaults:

- ``from``: the identity's last decided snapshot other than the
  current digest (latest acceptance, else latest rejection,
  :func:`app.domain.approval.last_decided`); else the record's
  ``previous_digest``; else there is no base (``reason:
  "no_prior_revision"``).
- ``to``: the record's current digest.

Only digests related to the record may be requested: its current and
previous digest, digests decided for its identity, and the current
digests of its identity siblings. Any other digest is answered with
404 ``unknown_revision``, so the endpoint cannot be used to read
arbitrary snapshots.

Public API: :class:`DiffEndpoint`, :class:`RecordDiff`,
:func:`diff_record`, :func:`short_digest`.
"""

import datetime
import difflib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.approval import DecisionAction, last_decided
from app.errors import NotFoundError
from app.storage.port import CatalogStore, DecisionEvent, StoredRecord

__all__ = ["DiffEndpoint", "RecordDiff", "diff_record", "short_digest"]

_SHORT_HEX = 12


@dataclass(frozen=True, slots=True, kw_only=True)
class DiffEndpoint:
    """
    One side of a diff.

    :param digest: Digest of the snapshot.
    :param label: What the snapshot is, e.g. ``last accepted``,
        ``last rejected``, ``previous revision``, ``current revision``.
    :param decided_at: When it was decided, for decided snapshots.
    """

    digest: str
    label: str
    decided_at: datetime.datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordDiff:
    """
    A unified diff between two snapshots of one record's identity.

    :param base: The ``from`` side, ``None`` without a prior revision.
    :param target: The ``to`` side.
    :param reason: ``no_prior_revision`` when there is no base.
    :param unified_diff: ``difflib`` unified diff text (empty when the
        snapshots are identical or there is no base).
    :param identical: Whether both snapshots are the same content.
    :param lines_added: Number of added lines.
    :param lines_removed: Number of removed lines.
    """

    base: DiffEndpoint | None
    target: DiffEndpoint
    reason: str | None
    unified_diff: str
    identical: bool
    lines_added: int
    lines_removed: int


def short_digest(digest: str) -> str:
    """
    Shorten a digest for display (algorithm prefix kept).

    :param digest: Full digest string.
    :returns: ``<algorithm>:<first 12 hex>``.
    """
    algorithm, _, hexdigest = digest.partition(":")
    return f"{algorithm}:{hexdigest[:_SHORT_HEX]}"


def _latest_event(
    events: Sequence[DecisionEvent], digest: str
) -> DecisionEvent | None:
    """Latest decision for *digest*, if any."""
    matching = [e for e in events if e.digest == digest]
    return max(matching, key=lambda e: (e.created_at, e.id), default=None)


def _endpoint(
    record: StoredRecord,
    events: Sequence[DecisionEvent],
    digest: str,
) -> DiffEndpoint:
    """
    Label a digest relative to the record.

    :param record: The viewed record.
    :param events: Every decision event of its identity.
    :param digest: The digest to label.
    :returns: The labelled endpoint.
    """
    if digest == record.digest:
        return DiffEndpoint(digest=digest, label="current revision")
    event = _latest_event(events, digest)
    if event is not None:
        default = last_decided(
            [e.as_view() for e in events], exclude_digest=record.digest
        )
        accepted = event.action is DecisionAction.ACCEPTED
        word = "accepted" if accepted else "rejected"
        prefix = "last " if default and default.digest == digest else ""
        return DiffEndpoint(
            digest=digest, label=f"{prefix}{word}", decided_at=event.created_at
        )
    if digest == record.previous_digest:
        return DiffEndpoint(digest=digest, label="previous revision")
    return DiffEndpoint(digest=digest, label="other revision")


def _default_base(
    record: StoredRecord, events: Sequence[DecisionEvent]
) -> str | None:
    """Pick the default ``from`` digest (module docstring)."""
    decided = last_decided(
        [e.as_view() for e in events], exclude_digest=record.digest
    )
    if decided is not None:
        return decided.digest
    return record.previous_digest


def _allowed(
    record: StoredRecord,
    events: Sequence[DecisionEvent],
    siblings: Sequence[StoredRecord],
) -> set[str]:
    """Digests this record's diff may reference."""
    allowed = {record.digest, *(e.digest for e in events)}
    allowed |= {s.digest for s in siblings}
    if record.previous_digest:
        allowed.add(record.previous_digest)
    return allowed


def _content(store: CatalogStore, digest: str) -> str:
    """Read a snapshot or answer 404."""
    revision = store.get_revision(digest)
    if revision is None:
        raise NotFoundError(
            f"snapshot {short_digest(digest)} is not stored",
            code="unknown_revision",
        )
    return revision.content


def _unified(
    base: DiffEndpoint, target: DiffEndpoint, old: str, new: str
) -> tuple[str, int, int]:
    """
    Compute the unified diff text and line counts.

    :param base: The ``from`` side.
    :param target: The ``to`` side.
    :param old: Base snapshot text.
    :param new: Target snapshot text.
    :returns: ``(text, added, removed)``.
    """
    lines = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"{short_digest(base.digest)} ({base.label})",
            tofile=f"{short_digest(target.digest)} ({target.label})",
            lineterm="",
        )
    )
    body = lines[2:]
    added = sum(1 for line in body if line.startswith("+"))
    removed = sum(1 for line in body if line.startswith("-"))
    text = "\n".join(lines) + "\n" if lines else ""
    return text, added, removed


def diff_record(
    store: CatalogStore,
    record_id: uuid.UUID,
    *,
    from_digest: str | None = None,
    to_digest: str | None = None,
) -> RecordDiff:
    """
    Diff two snapshots of a record's identity.

    :param store: Store of the caller's unit of work.
    :param record_id: Record id.
    :param from_digest: Base digest; default per the module docstring.
    :param to_digest: Target digest; default the current digest.
    :returns: The diff.
    :raises NotFoundError: ``record_not_found`` or ``unknown_revision``.
    """
    record = store.get_record(record_id)
    if record is None:
        raise NotFoundError(
            f"record {record_id} not found", code="record_not_found"
        )
    events = store.list_decisions(record.identity)
    siblings = store.list_identity_siblings(record.identity)
    allowed = _allowed(record, events, siblings)
    for digest in (from_digest, to_digest):
        if digest is not None and digest not in allowed:
            raise NotFoundError(
                "this revision is not related to the record",
                code="unknown_revision",
                hint="use a digest from the record's history",
            )
    target = _endpoint(record, events, to_digest or record.digest)
    base_digest = from_digest or _default_base(record, events)
    new = _content(store, target.digest)
    if base_digest is None:
        return RecordDiff(
            base=None,
            target=target,
            reason="no_prior_revision",
            unified_diff="",
            identical=False,
            lines_added=0,
            lines_removed=0,
        )
    base = _endpoint(record, events, base_digest)
    old = _content(store, base.digest)
    text, added, removed = _unified(base, target, old, new)
    return RecordDiff(
        base=base,
        target=target,
        reason=None,
        unified_diff=text,
        identical=old == new,
        lines_added=added,
        lines_removed=removed,
    )
