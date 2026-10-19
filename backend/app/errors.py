"""Domain exception classes and their FastAPI handler registration.

Domain errors are plain Python exceptions raised by the service
layer. Routers never translate built-in exceptions (``ValueError``,
``KeyError``) into HTTP responses; instead every error condition that
can cross a layer boundary gets its own exception class here, mapped
to an explicit HTTP status code by a registered handler.


Error bodies are ``{"detail": "<message>"}``; errors constructed with
a machine-readable ``code`` add ``"code": "<code>"`` next to it (the
authentication and authorization errors always do).
"""

from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AdrianoError(Exception):
    """Base class for all domain exceptions raised by the services.

    :param message: Human-readable description of the error.
    :param code: Optional machine-readable error code.
    """

    def __init__(self, message: str, *, code: str | None = None) -> None:
        """
        Store the message and code.

        :param message: Human-readable description of the error.
        :param code: Optional machine-readable error code.
        """
        super().__init__(message)
        self.message = message
        self.code = code

    @property
    def headers(self) -> Mapping[str, str]:
        """
        Extra response headers for this error.

        :returns: Header names and values (none by default).
        """
        return {}


class ConfigurationError(AdrianoError):
    """Raised when ``catalog.yaml`` or a related setting is invalid."""


class NotFoundError(AdrianoError):
    """Raised when a requested catalog resource does not exist."""


class ConflictError(AdrianoError):
    """Raised when a write conflicts with existing state (HTTP 409)."""


class DecisionExistsError(ConflictError):
    """Raised when the identity already has a decision for the digest."""


class CandidateExistsError(ConflictError):
    """Raised when a create-only candidate write finds an existing row."""


class DeliveryExistsError(ConflictError):
    """Raised when an intake run with the same delivery id exists."""


class ForbiddenError(AdrianoError):
    """Raised when the caller lacks permission for an action."""


class ValidationFailedError(AdrianoError):
    """Raised when submitted content fails validation (HTTP 422)."""


class AuthenticationError(AdrianoError):
    """
    Raised when a request has no acceptable bearer token (HTTP 401).

    The response carries ``WWW-Authenticate: Bearer`` (RFC 6750), with
    ``error="invalid_token"`` when a token was presented.

    :param message: Human-readable reason (never contains the token).
    :param code: Machine-readable error code.
    :param token_presented: Whether the request carried a token.
    """

    def __init__(
        self, message: str, *, code: str, token_presented: bool = True
    ) -> None:
        """
        Store the reason.

        :param message: Human-readable reason.
        :param code: Machine-readable error code.
        :param token_presented: Whether the request carried a token.
        """
        super().__init__(message, code=code)
        self.token_presented = token_presented

    @property
    def headers(self) -> Mapping[str, str]:
        """
        Build the ``WWW-Authenticate`` challenge.

        :returns: The challenge header.
        """
        if self.token_presented:
            return {"WWW-Authenticate": 'Bearer error="invalid_token"'}
        return {"WWW-Authenticate": "Bearer"}


class AuthUnavailableError(AdrianoError):
    """
    Raised when the server cannot authenticate anyone (HTTP 503).

    Either no authentication mechanism is configured, or the identity
    provider's discovery document or keys cannot be fetched.
    """


_STATUS_BY_ERROR: dict[type[AdrianoError], int] = {
    ConfigurationError: 500,
    AuthenticationError: 401,
    AuthUnavailableError: 503,
    NotFoundError: 404,
    ConflictError: 409,
    ForbiddenError: 403,
    ValidationFailedError: 422,
}


def register_handlers(app: FastAPI) -> None:
    """Register exception handlers for every domain error class.

    :param app: The FastAPI application under construction.
    """
    for error_type, status_code in _STATUS_BY_ERROR.items():
        app.add_exception_handler(error_type, _make_handler(status_code))


def _make_handler(
    status_code: int,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """Build a handler closure for one domain-error status code.

    :param status_code: HTTP status code to return for this error
        class.
    :returns: An async FastAPI exception handler.
    """

    async def _handler(_request: Request, exc: Exception) -> JSONResponse:
        """Map a domain exception to a JSON error response.

        :param _request: The incoming request (unused).
        :param exc: The raised domain exception.
        :returns: A JSON response carrying the error detail.
        """
        if not isinstance(exc, AdrianoError):
            return JSONResponse(
                status_code=status_code, content={"detail": str(exc)}
            )
        content = {"detail": exc.message}
        if exc.code is not None:
            content["code"] = exc.code
        return JSONResponse(
            status_code=status_code,
            content=content,
            headers=dict(exc.headers),
        )

    return _handler
