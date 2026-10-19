"""
CI push intake: ``PUT`` / ``POST /api/v1/candidates``.

A pushed document goes through the same parse -> validate -> hash ->
persist path as a polled one (:mod:`app.services.ingest`), always as a
**candidate** row: a push can never write, replace or delete a
published row, and never touches approval history. Source adapters are
never called.

Checks, in this order (each failure is answered with a stable ``code``
and a ``hint``; see ``docs``/the router for the HTTP status):

1. no bearer token -> 401 ``not_authenticated``;
2. the token is not a push token of the named registration (unknown or
   disabled registrations have none) -> 401 ``invalid_push_token``.
   Authentication comes first, so an unauthenticated caller learns
   nothing about which registrations exist or what the body should
   contain (a request without a usable ``source_id`` is authenticated
   against every registration before it is refused);
3. body larger than :data:`MAX_BODY_BYTES` -> 413 ``payload_too_large``;
4. malformed body (not JSON, missing/extra/invalid fields; a
   client-supplied ``digest`` is an unexpected field) -> 422
   ``invalid_request``;
5. registration lacks ``push`` intake -> 403 ``push_disabled``;
6. project outside the registration scope -> 403
   ``project_out_of_scope``;
7. ``ref`` equals the configured ``published_ref`` -> 422
   ``published_ref_not_allowed``. A leading ``refs/heads/`` is ignored
   on both sides. For ``published_ref: "@project-default"`` (GitLab)
   the real default branch is unknown without a source call, which
   intake never makes: only the literal value is refused, and a push
   to the default branch is stored as a candidate (documented
   limitation; polling still owns the published row);
8. ``delivery_id`` already received for the registration -> the
   earlier result (``deduplicated: true``), nothing is re-ingested
   (checked again under the registration lock against races);
9. content larger than :data:`MAX_CONTENT_BYTES` (UTF-8) -> 413
   ``content_too_large``; content that cannot be encoded as UTF-8
   (lone surrogates) -> 422 ``bad_encoding``;
10. document without usable frontmatter or UUID -> 422
    ``invalid_document`` with the ``issues`` list; document UUID other
    than ``adr_uuid`` -> 422 ``uuid_mismatch``;
11. ``POST`` and the candidate ``(source_id, project, adr_uuid, ref)``
    exists -> 409 ``candidate_exists``.

Every request records an ``intake_run`` (kind ``push``): successes
(also deduplicated ones) with the outcome in ``counts``, failures with
``errors``. The token is never stored; ``source_id`` is stored as
requested (truncated), possibly naming no registration.
``delivery_id`` is stored only on the successful run, so a failed
delivery can be retried with the same id.

Public API: :data:`MAX_BODY_BYTES`, :data:`MAX_CONTENT_BYTES` and
:class:`CandidateSubmission` (re-exported from
:mod:`app.services.intake_checks`), :class:`IntakeMode`,
:class:`IntakeResult`, :func:`submit_candidate`.
"""

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.frontmatter import JsonValue
from app.domain.issues import Issue
from app.errors import (
    AdrianoError,
    CandidateExistsError,
    ConflictError,
    PayloadTooLargeError,
)
from app.services.ingest import (
    PreparedDocument,
    ingest_document,
    prepare_document,
)
from app.services.intake_checks import (
    MAX_BODY_BYTES,
    MAX_CONTENT_BYTES,
    CandidateSubmission,
    auth_error,
    authenticate,
    build_document,
    check_document,
    check_registration,
    decode_body,
    issues_json,
    named_source,
    peek_source_id,
    validate_submission,
)
from app.source_config import SourceRegistration
from app.storage.port import (
    CatalogStore,
    CatalogStoreProvider,
    IntakeKind,
    IntakeRun,
    IntakeStatus,
    RecordState,
)

__all__ = [
    "MAX_BODY_BYTES",
    "MAX_CONTENT_BYTES",
    "CandidateSubmission",
    "IntakeMode",
    "IntakeResult",
    "submit_candidate",
]

logger = logging.getLogger(__name__)

_MAX_LOGGED_ID = 128


class IntakeMode(StrEnum):
    """``PUT`` (create or replace) or ``POST`` (create only)."""

    REPLACE = "put"
    CREATE = "post"


@dataclass(frozen=True, slots=True, kw_only=True)
class IntakeResult:
    """
    Outcome of one candidate submission.

    :param record_id: Candidate row id.
    :param digest: Server-computed canonical digest.
    :param created: A new candidate row was inserted.
    :param updated: An existing candidate got new content.
    :param deduplicated: The delivery id was seen before; nothing was
        ingested and this is the earlier result.
    :param issues: Per-document validation issues (non-blocking).
    """

    record_id: uuid.UUID
    digest: str
    created: bool
    updated: bool
    deduplicated: bool
    issues: tuple[Issue, ...]


@dataclass(slots=True)
class _Attempt:
    """What is known about a request, for its ``intake_run`` row."""

    mode: IntakeMode
    source_id: str = ""
    identity: dict[str, JsonValue] = field(default_factory=dict)


def _counts(result: IntakeResult) -> dict[str, JsonValue]:
    """Serialise a result into the ``intake_run.counts`` JSON."""
    return {
        "created": int(result.created),
        "updated": int(result.updated),
        "unchanged": int(not (result.created or result.updated)),
        "deduplicated": result.deduplicated,
        "record_id": str(result.record_id),
        "digest": result.digest,
        "issues": issues_json(result.issues),
    }


def _from_run(run: IntakeRun) -> IntakeResult | None:
    """Rebuild the result of an earlier successful run, if possible."""
    counts = run.counts
    if run.status is not IntakeStatus.OK or not isinstance(counts, dict):
        return None
    issues = counts.get("issues")
    return IntakeResult(
        record_id=uuid.UUID(str(counts["record_id"])),
        digest=str(counts["digest"]),
        created=bool(counts.get("created")),
        updated=bool(counts.get("updated")),
        deduplicated=True,
        issues=tuple(
            Issue.from_dict(item)  # pyright: ignore[reportArgumentType]
            for item in (issues if isinstance(issues, list) else [])
        ),
    )


def _earlier(
    store: CatalogStore, source_id: str, delivery_id: str | None
) -> IntakeResult | None:
    """Find the earlier result of a delivery id, if any."""
    if delivery_id is None:
        return None
    run = store.find_intake_run(source_id, delivery_id)
    return None if run is None else _from_run(run)


def _log_run(
    store: CatalogStore, attempt: _Attempt, result: IntakeResult
) -> None:
    """Record a successful run without a delivery id (dedup answers)."""
    run = store.start_intake_run(
        attempt.source_id, IntakeKind.PUSH, identity=attempt.identity
    )
    store.finish_intake_run(run.id, IntakeStatus.OK, counts=_counts(result))


def _ingest(
    provider: CatalogStoreProvider,
    prepared: PreparedDocument,
    submission: CandidateSubmission,
    attempt: _Attempt,
) -> IntakeResult:
    """
    Store the candidate and its run log under the registration lock.

    :param provider: Storage provider.
    :param prepared: Parsed, checked document.
    :param submission: The validated body.
    :param attempt: Run-log context.
    :returns: The outcome.
    :raises app.errors.CandidateExistsError: ``POST`` on an existing
        candidate.
    """
    with provider.lock_registration(submission.source_id) as store:
        earlier = _earlier(store, submission.source_id, submission.delivery_id)
        if earlier is not None:
            _log_run(store, attempt, earlier)
            return earlier
        run = store.start_intake_run(
            submission.source_id,
            IntakeKind.PUSH,
            identity=attempt.identity,
            delivery_id=submission.delivery_id,
        )
        outcome = ingest_document(
            store,
            prepared,
            RecordState.CANDIDATE,
            create_only=attempt.mode is IntakeMode.CREATE,
        )
        result = IntakeResult(
            record_id=outcome.record_id,
            digest=outcome.digest,
            created=outcome.created,
            updated=outcome.digest_changed,
            deduplicated=False,
            issues=outcome.issues,
        )
        store.finish_intake_run(run.id, IntakeStatus.OK, counts=_counts(result))
    return result


def _identity(
    submission: CandidateSubmission, mode: IntakeMode
) -> dict[str, JsonValue]:
    """Describe a submission for the run log (no content, no token)."""
    return {
        "via": "push_token",
        "mode": mode.value,
        "project": submission.project,
        "adr_uuid": str(submission.adr_uuid),
        "ref": submission.ref,
        "path": submission.path,
        "author": submission.author,
        "delivery_id": submission.delivery_id,
    }


def _submit(
    provider: CatalogStoreProvider,
    sources: Sequence[SourceRegistration],
    token: str | None,
    body: bytes,
    attempt: _Attempt,
) -> IntakeResult:
    """Run the checks of the module docstring, then ingest."""
    if not token:
        raise auth_error("a push token is required", presented=False)
    oversized = len(body) > MAX_BODY_BYTES
    raw = None if oversized else decode_body(body)
    source_id = peek_source_id(raw)
    attempt.source_id = (source_id or "")[:_MAX_LOGGED_ID]
    authenticate(sources, token, source_id)
    if oversized:
        raise PayloadTooLargeError(
            f"the request body exceeds {MAX_BODY_BYTES} bytes",
            code="payload_too_large",
            hint="ADR files must be at most 1 MiB",
        )
    submission = validate_submission(raw)
    attempt.identity = _identity(submission, attempt.mode)
    source = named_source(sources, token, submission.source_id)
    check_registration(source, submission)
    with provider.unit_of_work() as store:
        earlier = _earlier(store, source.id, submission.delivery_id)
        if earlier is not None:
            _log_run(store, attempt, earlier)
            return earlier
    prepared = prepare_document(build_document(source, submission))
    check_document(prepared, submission)
    return _ingest(provider, prepared, submission, attempt)


def _record_failure(
    provider: CatalogStoreProvider, attempt: _Attempt, error: AdrianoError
) -> None:
    """
    Record a failed request in its own unit of work (never raises).

    :param provider: Storage provider.
    :param attempt: Run-log context.
    :param error: The refusal.
    """
    errors: list[JsonValue] = [{"code": error.code, "message": error.message}]
    identity: Mapping[str, JsonValue] = attempt.identity or {
        "via": "push_token",
        "mode": attempt.mode.value,
    }
    try:
        with provider.unit_of_work() as store:
            run = store.start_intake_run(
                attempt.source_id, IntakeKind.PUSH, identity=dict(identity)
            )
            store.finish_intake_run(run.id, IntakeStatus.FAILED, errors=errors)
    except Exception:  # the refusal itself must still reach the caller
        logger.exception("could not record a failed push intake run")


def submit_candidate(
    provider: CatalogStoreProvider,
    sources: Sequence[SourceRegistration],
    *,
    token: str | None,
    body: bytes,
    mode: IntakeMode,
) -> IntakeResult:
    """
    Authenticate, validate and ingest one pushed candidate.

    Blocking (synchronous database calls): call it from a worker thread.

    :param provider: Storage provider.
    :param sources: Configured registrations.
    :param token: Bearer token of the request, if any.
    :param body: Raw request body (read with a cap slightly above
        :data:`MAX_BODY_BYTES`).
    :param mode: ``PUT`` or ``POST`` semantics.
    :returns: The outcome.
    :raises app.errors.AdrianoError: The refusals listed in the module
        docstring; each one is recorded as a failed ``intake_run``.
    """
    attempt = _Attempt(mode)
    try:
        return _submit(provider, sources, token, body, attempt)
    except CandidateExistsError as exc:
        error = ConflictError(
            "a candidate for this source, project, ADR and ref exists",
            code="candidate_exists",
            hint="use PUT to replace an existing candidate",
        )
        _record_failure(provider, attempt, error)
        raise error from exc
    except AdrianoError as exc:
        _record_failure(provider, attempt, exc)
        raise
