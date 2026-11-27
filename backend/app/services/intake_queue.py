"""
The holder rule and the not-indexed list for CI push intake.

An ADR's UUID is held by the file already indexed under it (its
published row). A push may carry a UUID that nobody holds, or one whose
published holder lives in the **same registration and project** as the
push (the same repository, so a branch of the holder's own file). Any
other push claims a UUID held elsewhere and is refused:
:func:`ensure_not_held_elsewhere` raises ``duplicate_uuid`` (409). The
message names the UUID but not where it is held: the caller holds only
a push token of its own registration.

Every refused push that concerns a document is written to the
not-indexed list (:func:`queue_rejection`), keyed by the location the
push named (``source_id``, ``project``, the path or its synthesised
default, ``ref``), with origin ``push``, the reasons, and the content
(as a revision) whenever the body carried a decodable document of
acceptable size. These refusals are queued:
``published_ref_not_allowed``, ``bad_encoding``, ``content_too_large``,
``invalid_document``, ``uuid_mismatch`` and ``duplicate_uuid``. Not
queued are refusals that
say nothing about the document: authentication, malformed requests,
``push_disabled`` and ``project_out_of_scope`` (the location is not the
registration's), and ``candidate_exists`` (the candidate is indexed).

A later successful push for the same location removes its push entry
(:func:`clear_push_entry`); only that, and a poll indexing a document
at the same file location (:mod:`app.services.poll_apply`, any ref,
any reason), ever remove one.

Public API: :func:`ensure_not_held_elsewhere`, :func:`queue_rejection`,
:func:`clear_push_entry`.
"""

from app.domain.issues import Issue, IssueCode, error
from app.errors import AdrianoError, ConflictError
from app.services.ingest import PreparedDocument, prepare_document
from app.services.intake_checks import (
    CandidateSubmission,
    build_document,
    document_path,
)
from app.source_config import SourceRegistration
from app.storage.port import (
    CatalogStore,
    IntakeKind,
    NotIndexedKey,
    NotIndexedWrite,
)

__all__ = [
    "clear_push_entry",
    "ensure_not_held_elsewhere",
    "queue_rejection",
]

#: Refusal code -> issue code of the not-indexed reason. ``None``: the
#: reasons are those of the parsed document.
_REASONS: dict[str, IssueCode | None] = {
    "published_ref_not_allowed": IssueCode.PUBLISHED_REF_NOT_ALLOWED,
    "bad_encoding": IssueCode.BAD_ENCODING,
    "content_too_large": IssueCode.CONTENT_TOO_LARGE,
    "invalid_document": None,
    "uuid_mismatch": IssueCode.UUID_MISMATCH,
    "duplicate_uuid": IssueCode.DUPLICATE_UUID,
}


def ensure_not_held_elsewhere(
    store: CatalogStore,
    source: SourceRegistration,
    submission: CandidateSubmission,
) -> None:
    """
    Refuse a UUID whose published holder is in another project.

    :param store: Store of the caller's (locked) unit of work.
    :param source: The authenticated registration.
    :param submission: The validated body.
    :raises app.errors.ConflictError: ``duplicate_uuid``.
    """
    holder = store.get_published(submission.adr_uuid)
    if holder is None:
        return
    if (holder.source_id, holder.project) == (source.id, submission.project):
        return
    raise ConflictError(
        f"UUID {submission.adr_uuid} is already held by another ADR "
        "file of the catalog",
        code="duplicate_uuid",
        hint="give the file its own UUID, or push it to the project that "
        "holds this ADR",
    )


def _prepared(
    source: SourceRegistration, submission: CandidateSubmission
) -> PreparedDocument | None:
    """
    Prepare the pushed content, if it can be stored.

    :param source: The registration.
    :param submission: The validated body.
    :returns: The prepared document; ``None`` for content that cannot be
        encoded or is too large.
    """
    try:
        return prepare_document(build_document(source, submission))
    except AdrianoError:
        return None


def _reasons(
    refusal: AdrianoError, prepared: PreparedDocument | None
) -> tuple[Issue, ...]:
    """
    Build the not-indexed reasons of a refusal.

    :param refusal: The refusal (its code is in :data:`_REASONS`).
    :param prepared: The prepared document, if any.
    :returns: The reasons.
    """
    code = _REASONS[refusal.code or ""]
    if code is None and prepared is not None and prepared.reasons:
        return prepared.reasons
    return (error(code or IssueCode.MISSING_FRONTMATTER, refusal.message),)


def queue_rejection(
    store: CatalogStore,
    source: SourceRegistration,
    submission: CandidateSubmission,
    refusal: AdrianoError,
) -> bool:
    """
    Write a refused push to the not-indexed list, if it belongs there.

    :param store: Store of the caller's unit of work.
    :param source: The authenticated registration.
    :param submission: The validated body.
    :param refusal: Why the push was refused.
    :returns: Whether an entry was written (see the module docstring).
    """
    if refusal.code not in _REASONS:
        return False
    prepared = _prepared(source, submission)
    if prepared is not None:
        store.put_revision(prepared.digest, prepared.text)
    store.put_not_indexed(
        NotIndexedWrite(
            key=_key(source, submission),
            origin=IntakeKind.PUSH,
            reasons=_reasons(refusal, prepared),
            digest=None if prepared is None else prepared.digest,
            holder_uuid=(
                submission.adr_uuid
                if refusal.code == "duplicate_uuid"
                else None
            ),
        )
    )
    return True


def _key(
    source: SourceRegistration, submission: CandidateSubmission
) -> NotIndexedKey:
    """Build the location key a push names."""
    return NotIndexedKey(
        source.id,
        submission.project,
        document_path(source, submission),
        submission.ref,
    )


def clear_push_entry(
    store: CatalogStore,
    source: SourceRegistration,
    submission: CandidateSubmission,
) -> None:
    """
    Remove the push entry of the location a push just succeeded at.

    :param store: Store of the caller's (locked) unit of work.
    :param source: The authenticated registration.
    :param submission: The validated body of the accepted push.
    """
    key = _key(source, submission)
    entry = store.get_not_indexed(key)
    if entry is not None and entry.origin is IntakeKind.PUSH:
        store.delete_not_indexed([key])
