"""Domain exception classes and their FastAPI handler registration.

Domain errors are plain Python exceptions raised by the service
layer. Routers never translate built-in exceptions (``ValueError``,
``KeyError``) into HTTP responses; instead every error condition that
can cross a layer boundary gets its own exception class here, mapped
to an explicit HTTP status code by a registered handler.


Error bodies are ``{"detail": "<message>"}``; errors constructed with
a machine-readable ``code`` add ``"code": "<code>"`` next to it (the
authentication and authorization errors always do). An optional
``hint`` (what the caller or an operator can do about it) adds
``"hint": "<hint>"``, and ``extra`` adds further JSON members (for
example the ``issues`` list of a refused candidate document).
"""

from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.frontmatter import JsonValue


class AdrianoError(Exception):
    """Base class for all domain exceptions raised by the services.

    :param message: Human-readable description of the error.
    :param code: Optional machine-readable error code.
    :param hint: Optional recovery advice for the caller or operator.
    :param extra: Optional further JSON members of the error body.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        hint: str | None = None,
        extra: Mapping[str, JsonValue] | None = None,
    ) -> None:
        """
        Store the message, code, hint and extra members.

        :param message: Human-readable description of the error.
        :param code: Optional machine-readable error code.
        :param hint: Optional recovery advice.
        :param extra: Optional further JSON members of the error body.
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.hint = hint
        self.extra: Mapping[str, JsonValue] = dict(extra or {})

    def body(self) -> dict[str, JsonValue]:
        """
        Build the JSON error body.

        :returns: ``detail`` plus ``code``/``hint`` when set, plus
            :attr:`extra`.
        """
        content: dict[str, JsonValue] = {"detail": self.message}
        if self.code is not None:
            content["code"] = self.code
        if self.hint is not None:
            content["hint"] = self.hint
        for key, value in self.extra.items():
            content.setdefault(key, value)
        return content

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


class PayloadTooLargeError(AdrianoError):
    """Raised when a request body or document exceeds a limit (HTTP 413)."""


class AuthenticationError(AdrianoError):
    """
    Raised when a request has no acceptable credentials (HTTP 401).

    Credentials are the session cookie on user routes and a push token
    on candidate intake. The response carries ``WWW-Authenticate:
    Bearer`` (RFC 6750), with ``error="invalid_token"`` when credentials
    were presented.

    :param message: Human-readable reason (never contains a secret).
    :param code: Machine-readable error code.
    :param token_presented: Whether the request carried credentials.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str,
        token_presented: bool = True,
        hint: str | None = None,
    ) -> None:
        """
        Store the reason.

        :param message: Human-readable reason.
        :param code: Machine-readable error code.
        :param token_presented: Whether the request carried a token.
        :param hint: Optional recovery advice.
        """
        super().__init__(message, code=code, hint=hint)
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
    PayloadTooLargeError: 413,
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
        return JSONResponse(
            status_code=status_code,
            content=exc.body(),
            headers=dict(exc.headers),
        )

    return _handler
