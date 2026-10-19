"""Domain exception classes and their FastAPI handler registration.

Domain errors are plain Python exceptions raised by the service
layer. Routers never translate built-in exceptions (``ValueError``,
``KeyError``) into HTTP responses; instead every error condition that
can cross a layer boundary gets its own exception class here, mapped
to an explicit HTTP status code by a registered handler.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AdrianoError(Exception):
    """Base class for all domain exceptions raised by the services.

    :param message: Human-readable description of the error.
    """

    def __init__(self, message: str) -> None:
        """:param message: Human-readable description of the error."""
        super().__init__(message)
        self.message = message


class ConfigurationError(AdrianoError):
    """Raised when ``catalog.yaml`` or a related setting is invalid."""


class NotFoundError(AdrianoError):
    """Raised when a requested catalog resource does not exist."""


class ConflictError(AdrianoError):
    """Raised when a write conflicts with existing state (HTTP 409)."""


class ForbiddenError(AdrianoError):
    """Raised when the caller lacks permission for an action."""


class ValidationFailedError(AdrianoError):
    """Raised when submitted content fails validation (HTTP 422)."""


_STATUS_BY_ERROR: dict[type[AdrianoError], int] = {
    ConfigurationError: 500,
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
) -> Callable[[Request, AdrianoError], Awaitable[JSONResponse]]:
    """Build a handler closure for one domain-error status code.

    :param status_code: HTTP status code to return for this error
        class.
    :returns: An async FastAPI exception handler.
    """

    async def _handler(_request: Request, exc: AdrianoError) -> JSONResponse:
        """Map a domain exception to a JSON error response.

        :param _request: The incoming request (unused).
        :param exc: The raised domain exception.
        :returns: A JSON response carrying the error detail.
        """
        return JSONResponse(
            status_code=status_code, content={"detail": exc.message}
        )

    return _handler
