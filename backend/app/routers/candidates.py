"""
CI push intake: ``PUT`` and ``POST /api/v1/candidates``.

Authenticated with a per-registration **push token** (``Authorization:
Bearer <token>``), never with OIDC: see :mod:`app.auth.push`. All
checks, error codes and the run log live in
:mod:`app.services.intake`; this router only reads the body (with a
size cap, before parsing, so authentication can come first) and maps
the outcome to a status code:

- ``PUT``: 201 when the candidate was created, else 200 (replaced or
  unchanged); idempotent for identical content.
- ``POST``: 201, or 409 ``candidate_exists``.
- A repeated ``delivery_id``: 200 with ``deduplicated: true``.

The request body schema is :class:`~app.services.intake.
CandidateSubmission`, published in OpenAPI through ``openapi_extra``.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.composition import (
    CatalogRuntime,
    get_catalog_runtime,
    get_store_provider,
)
from app.schemas.approval import CandidateResultOut
from app.schemas.records import IssueOut
from app.services.intake import (
    MAX_BODY_BYTES,
    CandidateSubmission,
    IntakeMode,
    IntakeResult,
    submit_candidate,
)
from app.storage.port import CatalogStoreProvider

router = APIRouter(prefix="/api/v1", tags=["candidates"])

_push_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="PushToken",
    description="CI push token of the source registration (not OIDC).",
)

_OPENAPI: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": CandidateSubmission.model_json_schema()
            }
        },
    }
}

_ERROR = {"description": "Error body `{detail, code, hint}`."}
_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: _ERROR,
    403: _ERROR,
    409: _ERROR,
    413: _ERROR,
    422: _ERROR,
}


async def _read_body(request: Request) -> bytes:
    """
    Read the request body, stopping just past :data:`MAX_BODY_BYTES`.

    :param request: The request.
    :returns: The body, or its first ``MAX_BODY_BYTES + n`` bytes when
        larger (the service then answers 413).
    """
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        chunks.append(chunk)
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            break
    return b"".join(chunks)


def _out(result: IntakeResult) -> CandidateResultOut:
    """
    Convert the service result to the response model.

    :param result: The intake outcome.
    :returns: The response body.
    """
    return CandidateResultOut(
        record_id=result.record_id,
        digest=result.digest,
        created=result.created,
        updated=result.updated,
        deduplicated=result.deduplicated,
        issues=[IssueOut.model_validate(issue) for issue in result.issues],
        catalog_path=f"/records/{result.record_id}",
    )


async def _submit(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None,
    provider: CatalogStoreProvider,
    runtime: CatalogRuntime | None,
    mode: IntakeMode,
) -> CandidateResultOut:
    """
    Run the intake service in a worker thread and set the status code.

    :param request: The request (body source).
    :param response: The response (status code).
    :param credentials: Bearer credentials, if any.
    :param provider: Storage provider.
    :param runtime: Startup configuration state.
    :param mode: ``PUT`` or ``POST`` semantics.
    :returns: The response body.
    """
    token = credentials.credentials if credentials is not None else None
    body = await _read_body(request) if token else b""
    sources = runtime.config.sources if runtime is not None else ()
    result = await run_in_threadpool(
        submit_candidate,
        provider,
        sources,
        token=token,
        body=body,
        mode=mode,
    )
    created = result.created and not result.deduplicated
    response.status_code = 201 if created else 200
    return _out(result)


@router.put(
    "/candidates",
    response_model=CandidateResultOut,
    openapi_extra=_OPENAPI,
    responses=_RESPONSES,
)
async def put_candidate(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_push_bearer),
    provider: CatalogStoreProvider = Depends(get_store_provider),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
) -> CandidateResultOut:
    """
    Create or replace the candidate for (source, project, ADR, ref).

    :param request: The request.
    :param response: The response.
    :param credentials: Push-token bearer credentials.
    :param provider: Storage provider (overridden by tests).
    :param runtime: Startup configuration state.
    :returns: Record id, server digest, issues and catalog path.
    """
    return await _submit(
        request, response, credentials, provider, runtime, IntakeMode.REPLACE
    )


@router.post(
    "/candidates",
    response_model=CandidateResultOut,
    status_code=201,
    openapi_extra=_OPENAPI,
    responses=_RESPONSES,
)
async def post_candidate(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_push_bearer),
    provider: CatalogStoreProvider = Depends(get_store_provider),
    runtime: CatalogRuntime | None = Depends(get_catalog_runtime),
) -> CandidateResultOut:
    """
    Create a candidate; 409 ``candidate_exists`` if it already exists.

    :param request: The request.
    :param response: The response.
    :param credentials: Push-token bearer credentials.
    :param provider: Storage provider (overridden by tests).
    :param runtime: Startup configuration state.
    :returns: Record id, server digest, issues and catalog path.
    """
    return await _submit(
        request, response, credentials, provider, runtime, IntakeMode.CREATE
    )
