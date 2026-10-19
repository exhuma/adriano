"""
Request validation and refusal checks of CI push intake.

Pure helpers used by :mod:`app.services.intake` (which owns the
order of the checks, the run log and the write); see that module's
docstring for the full contract. Nothing here touches storage.

Public API: :data:`MAX_BODY_BYTES`, :data:`MAX_CONTENT_BYTES`,
:class:`CandidateSubmission`, :func:`auth_error`,
:func:`peek_source_id`, :func:`decode_body`, :func:`authenticate`,
:func:`named_source`, :func:`validate_submission`,
:func:`check_registration`, :func:`build_document`,
:func:`check_document`, :func:`issues_json`.
"""

import json
import uuid
from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

from app.auth.push import registrations_for_token, token_matches
from app.domain.frontmatter import JsonValue
from app.domain.issues import Issue, IssueCode
from app.errors import (
    AuthenticationError,
    ForbiddenError,
    PayloadTooLargeError,
    ValidationFailedError,
)
from app.services.ingest import IncomingDocument, PreparedDocument
from app.source_config import SourceRegistration
from app.storage.port import IntakeKind

__all__ = [
    "MAX_BODY_BYTES",
    "MAX_CONTENT_BYTES",
    "CandidateSubmission",
    "auth_error",
    "authenticate",
    "build_document",
    "check_document",
    "check_registration",
    "decode_body",
    "issues_json",
    "named_source",
    "peek_source_id",
    "validate_submission",
]

#: Largest accepted Markdown document (UTF-8 bytes).
MAX_CONTENT_BYTES = 1024 * 1024
#: Largest accepted request body (JSON escaping may inflate content).
MAX_BODY_BYTES = 8 * 1024 * 1024

#: Issue codes that make a pushed document unusable as a candidate.
_BLOCKING = frozenset(
    {
        IssueCode.MISSING_FRONTMATTER,
        IssueCode.BAD_YAML,
        IssueCode.MISSING_UUID,
        IssueCode.BAD_UUID,
        IssueCode.BAD_ENCODING,
    }
)

#: Plain alias (not ``type``) so the JSON schema inlines it.
_Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class CandidateSubmission(BaseModel):
    """Body of ``PUT``/``POST /api/v1/candidates``; extra keys -> 422."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    project: _Text = Field(description="Owning project path.")
    adr_uuid: uuid.UUID = Field(description="UUID of the pushed ADR.")
    ref: _Text = Field(description="Branch/ref the content comes from.")
    content: str = Field(description="The complete Markdown file.")
    path: str | None = Field(
        default=None,
        max_length=512,
        description=(
            "File path inside the project (for title/date fallbacks and "
            "provenance); default `<registration path>/<adr_uuid>.md`."
        ),
    )
    delivery_id: _Text | None = Field(
        default=None, description="CI event/delivery id for retry dedup."
    )
    author: Annotated[str, StringConstraints(max_length=320)] | None = Field(
        default=None, description="Author email (self-approval check)."
    )

    @field_validator("path")
    @classmethod
    def _relative_markdown(cls, value: str | None) -> str | None:
        """
        Require a project-relative ``.md`` path without ``..``.

        :param value: Submitted path.
        :returns: The path without surrounding slashes or whitespace.
        :raises ValueError: If the path is unusable.
        """
        if value is None:
            return None
        stripped = value.strip().strip("/")
        parts = PurePosixPath(stripped).parts
        if not stripped or ".." in parts or not stripped.endswith(".md"):
            raise ValueError("must be a relative `.md` path without `..`")
        return stripped


def auth_error(message: str, *, presented: bool) -> AuthenticationError:
    """
    Build the 401 for a missing or unacceptable push token.

    :param message: Reason (never contains the token).
    :param presented: Whether the request carried a token.
    :returns: The error.
    """
    return AuthenticationError(
        message,
        code="invalid_push_token" if presented else "not_authenticated",
        token_presented=presented,
        hint=(
            "send `Authorization: Bearer <push token>` with a token listed "
            "in the registration's `push_tokens_env`"
        ),
    )


def peek_source_id(raw: object) -> str | None:
    """
    Read ``source_id`` from a decoded body, if it is a string.

    :param raw: Decoded JSON body.
    :returns: The requested registration id, or ``None``.
    """
    if isinstance(raw, dict):
        value = raw.get("source_id")  # pyright: ignore[reportUnknownMemberType]
        if isinstance(value, str) and value:
            return value
    return None


def decode_body(body: bytes) -> object:
    """
    Decode a JSON body.

    :param body: Raw request body.
    :returns: The decoded value; ``None`` when it is not valid JSON.
    """
    try:
        return json.loads(body)
    except ValueError:
        return None


def authenticate(
    sources: Sequence[SourceRegistration], token: str, source_id: str | None
) -> SourceRegistration | None:
    """
    Check the push token against the named registration.

    :param sources: All configured registrations.
    :param token: Presented bearer token.
    :param source_id: Requested registration id, if the body names one.
    :returns: The registration; ``None`` when the body names none but
        the token is valid for some registration.
    :raises AuthenticationError: If the token is not acceptable.
    """
    if source_id is not None:
        return named_source(sources, token, source_id)
    if registrations_for_token(sources, token):
        return None
    raise auth_error("push token not accepted", presented=True)


def named_source(
    sources: Sequence[SourceRegistration], token: str, source_id: str
) -> SourceRegistration:
    """
    Check the push token against one registration.

    :param sources: All configured registrations.
    :param token: Presented bearer token.
    :param source_id: Requested registration id.
    :returns: The registration.
    :raises AuthenticationError: If the registration is unknown or the
        token is not one of its push tokens (same answer for both).
    """
    source = next((s for s in sources if s.id == source_id), None)
    tokens = source.push_tokens if source is not None else ()
    if source is None or not token_matches(tokens, token):
        raise auth_error(
            "push token not accepted for this source registration",
            presented=True,
        )
    return source


def validate_submission(raw: object) -> CandidateSubmission:
    """
    Validate the decoded body.

    :param raw: Decoded JSON (``None`` when the body was not JSON).
    :returns: The submission.
    :raises ValidationFailedError: ``invalid_request`` with ``errors``.
    """
    hint = "send the JSON body documented in the OpenAPI schema"
    if raw is None:
        raise ValidationFailedError(
            "the body is not valid JSON", code="invalid_request", hint=hint
        )
    try:
        return CandidateSubmission.model_validate(raw)
    except ValidationError as exc:
        errors: list[JsonValue] = [
            {
                "loc": [str(part) for part in error["loc"]],
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors(include_url=False, include_input=False)
        ]
        raise ValidationFailedError(
            "the request body is invalid",
            code="invalid_request",
            hint=hint + "; unexpected fields (e.g. `digest`) are refused",
            extra={"errors": errors},
        ) from exc


def _branch(ref: str) -> str:
    """Strip a leading ``refs/heads/`` for ref comparisons."""
    return ref.removeprefix("refs/heads/")


def check_registration(
    source: SourceRegistration, submission: CandidateSubmission
) -> None:
    """
    Check push intake, scope and ref against the registration.

    :param source: The authenticated registration.
    :param submission: The validated body.
    :raises ForbiddenError: ``push_disabled`` / ``project_out_of_scope``.
    :raises ValidationFailedError: ``published_ref_not_allowed``.
    """
    if IntakeKind.PUSH not in source.intake or source.binding is None:
        raise ForbiddenError(
            f"source {source.id!r} does not accept pushed candidates",
            code="push_disabled",
            hint="an operator must add `push` to the registration's `intake`",
        )
    if not source.binding.in_scope(submission.project):
        raise ForbiddenError(
            f"project {submission.project!r} is outside the scope of "
            f"source {source.id!r}",
            code="project_out_of_scope",
            hint="push to the registration that owns this project",
        )
    if _branch(submission.ref) == _branch(source.published_ref):
        raise ValidationFailedError(
            f"ref {submission.ref!r} is the published ref of {source.id!r}",
            code="published_ref_not_allowed",
            hint=(
                "published content is indexed by polling; push candidates "
                "from feature branches only"
            ),
        )


def build_document(
    source: SourceRegistration, submission: CandidateSubmission
) -> IncomingDocument:
    """
    Build the ingest input from a submission.

    :param source: The registration.
    :param submission: The validated body.
    :returns: The document.
    :raises PayloadTooLargeError: ``content_too_large``.
    :raises ValidationFailedError: ``bad_encoding``.
    """
    try:
        content = submission.content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationFailedError(
            "the content cannot be encoded as UTF-8",
            code="bad_encoding",
            hint="send the file as valid UTF-8 text",
        ) from exc
    if len(content) > MAX_CONTENT_BYTES:
        raise PayloadTooLargeError(
            f"the content exceeds {MAX_CONTENT_BYTES} bytes",
            code="content_too_large",
            hint="ADR files must be at most 1 MiB",
        )
    path = submission.path or f"{source.path}/{submission.adr_uuid}.md"
    return IncomingDocument(
        source_id=source.id,
        project=submission.project,
        path=path.strip("/"),
        ref=submission.ref,
        content=content,
        author=submission.author,
    )


def check_document(
    prepared: PreparedDocument, submission: CandidateSubmission
) -> None:
    """
    Refuse unusable documents and UUID mismatches.

    :param prepared: Parsed document.
    :param submission: The validated body.
    :raises ValidationFailedError: ``invalid_document`` (with
        ``issues``) or ``uuid_mismatch``.
    """
    issues = prepared.parsed.issues
    if any(issue.code in _BLOCKING for issue in issues):
        raise ValidationFailedError(
            "the document cannot be indexed",
            code="invalid_document",
            hint="fix the listed issues in the file's YAML frontmatter",
            extra={"issues": issues_json(issues)},
        )
    if prepared.parsed.adr_uuid != submission.adr_uuid:
        raise ValidationFailedError(
            f"the document uuid {prepared.parsed.adr_uuid} does not match "
            f"adr_uuid {submission.adr_uuid}",
            code="uuid_mismatch",
            hint="send the `uuid` from the file's frontmatter as adr_uuid",
        )


def issues_json(issues: Sequence[Issue]) -> list[JsonValue]:
    """
    Serialise issues to JSON values.

    :param issues: Validation issues.
    :returns: One ``{severity, code, message}`` object per issue.
    """
    return [dict(issue.to_dict()) for issue in issues]
