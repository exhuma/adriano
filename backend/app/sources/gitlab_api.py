"""
GitLab REST API v4 transport: client setup, retries, pagination, errors.

Used only by :mod:`app.sources.gitlab`. :func:`open_client` builds the
``httpx.AsyncClient`` (the shared outbound TLS context of
:mod:`app.tls`, so certificates are verified unless
``ADRIANO_TLS_VERIFY`` is false; timeouts, connection limits, no
redirects, token in the ``PRIVATE-TOKEN`` header).
:class:`GitLabApi` wraps it:

- **Bounded concurrency:** every HTTP request holds one permit of a
  semaphore of :data:`MAX_CONCURRENT_REQUESTS` (matching the connection
  pool size). A permit is held for one request only, never across
  pages or retry waits, so callers that already bound their own
  concurrency (the polling service) cannot deadlock with it.
- **Retries:** HTTP 429, any 5xx and transport errors (including
  timeouts) are retried up to :data:`MAX_ATTEMPTS` attempts in total,
  waiting ``BACKOFF_BASE * 2 ** (attempt - 1)`` seconds (capped at
  :data:`BACKOFF_CAP`) or the server's ``Retry-After`` (seconds or HTTP
  date, capped at :data:`RETRY_AFTER_CAP`). Exhausted retries raise
  :class:`~app.sources.port.SourceUnavailableError`.
- **Errors:** 401/403 raise
  :class:`~app.sources.port.SourceAccessError`, 404 raises
  :class:`~app.sources.port.SourceNotFoundError`, any other non-2xx
  raises :class:`~app.sources.port.SourceError`.
- **Pagination:** :meth:`GitLabApi.get_pages` follows the ``Link``
  ``rel="next"`` header (keyset and offset pagination) and falls back
  to ``X-Next-Page``. A next link outside the API root is refused, so
  the token is never sent to another origin.

The token is only ever placed in the client headers. Messages and log
lines name the request path (which never carries a secret) and the
token's env var name, never its value.

Public API: :data:`MAX_CONCURRENT_REQUESTS`, :data:`MAX_ATTEMPTS`,
:data:`BACKOFF_BASE`, :data:`BACKOFF_CAP`, :data:`RETRY_AFTER_CAP`,
:data:`PER_PAGE`, :data:`MAX_PAGES`, :data:`TIMEOUT`, :data:`Sleep`,
:func:`api_root`, :func:`open_client`, :func:`parse_model`,
:class:`GitLabApi`.
"""

import asyncio
import datetime
import email.utils
import logging
import ssl
from collections.abc import Awaitable, Callable, Mapping

import httpx
from pydantic import BaseModel, ValidationError

from app.sources.port import (
    SourceAccessError,
    SourceError,
    SourceNotFoundError,
    SourceUnavailableError,
)
from app.tls import outbound_ssl_context

#: Concurrent HTTP requests per adapter (also the connection pool size).
MAX_CONCURRENT_REQUESTS = 4
#: Attempts per request, including the first one.
MAX_ATTEMPTS = 4
#: First backoff wait in seconds (doubled per retry).
BACKOFF_BASE = 0.5
#: Longest computed backoff wait in seconds.
BACKOFF_CAP = 30.0
#: Longest honoured ``Retry-After`` wait in seconds.
RETRY_AFTER_CAP = 60.0
#: Items requested per page.
PER_PAGE = 100
#: Pages followed per listing before giving up (loop guard).
MAX_PAGES = 1000
#: Request timeouts (connect 10 s; read/write/pool 30 s).
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

#: Async sleep used for retry waits (injectable for tests).
type Sleep = Callable[[float], Awaitable[None]]

type QueryParams = Mapping[str, str | int]

logger = logging.getLogger(__name__)


def api_root(base_url: str) -> str:
    """
    Build the REST API v4 root of a GitLab instance.

    :param base_url: Instance URL without trailing slash.
    :returns: ``<base_url>/api/v4/``.
    """
    return f"{base_url}/api/v4/"


def open_client(
    base_url: str,
    token: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    ssl_context: ssl.SSLContext | None = None,
) -> httpx.AsyncClient:
    """
    Build the HTTP client of one poll.

    :param base_url: Instance URL without trailing slash.
    :param token: Access token (sent as ``PRIVATE-TOKEN``).
    :param transport: Transport override (tests use
        ``httpx.MockTransport``); ``None`` uses the default transport.
    :param ssl_context: TLS context (see :mod:`app.tls`); ``None``
        uses the default outbound context.
    :returns: The client; the caller closes it.
    """
    return httpx.AsyncClient(
        base_url=api_root(base_url),
        headers={"PRIVATE-TOKEN": token, "Accept": "application/json"},
        timeout=TIMEOUT,
        limits=httpx.Limits(
            max_connections=MAX_CONCURRENT_REQUESTS,
            max_keepalive_connections=MAX_CONCURRENT_REQUESTS,
        ),
        verify=ssl_context or outbound_ssl_context(),
        follow_redirects=False,
        transport=transport,
    )


def parse_model[M: BaseModel](model: type[M], data: object, what: str) -> M:
    """
    Validate one API object.

    :param model: Expected shape.
    :param data: Decoded JSON.
    :param what: Request description for the message.
    :returns: The model.
    :raises SourceUnavailableError: If the shape is unexpected.
    """
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise SourceUnavailableError(
            f"unexpected GitLab response for {what}"
        ) from exc


def _backoff(attempt: int) -> float:
    """
    Compute the exponential backoff wait after a failed attempt.

    :param attempt: Number of the failed attempt (1-based).
    :returns: Seconds to wait.
    """
    return float(min(BACKOFF_BASE * 2 ** (attempt - 1), BACKOFF_CAP))


def _retry_after(response: httpx.Response) -> float | None:
    """
    Read the ``Retry-After`` header.

    :param response: The response.
    :returns: Seconds to wait (capped), or ``None`` if absent/invalid.
    """
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(value)
        except TypeError, ValueError:
            return None
        now = datetime.datetime.now(datetime.UTC)
        seconds = (when - now).total_seconds()
    return min(max(seconds, 0.0), RETRY_AFTER_CAP)


def _is_retryable(status: int) -> bool:
    """
    Tell whether a status code is worth retrying.

    :param status: HTTP status.
    :returns: ``True`` for 429 and 5xx.
    """
    return status == 429 or status >= 500


class GitLabApi:
    """
    Retrying, concurrency-bounded GET access to the REST API.

    :param client: Client from :func:`open_client`.
    :param token_env: Env var name of the token (for messages only).
    :param sleep: Async sleep for retry waits.
    :param max_concurrency: Concurrent requests allowed.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        token_env: str,
        sleep: Sleep = asyncio.sleep,
        max_concurrency: int = MAX_CONCURRENT_REQUESTS,
    ) -> None:
        """
        Store the collaborators.

        :param client: HTTP client.
        :param token_env: Env var name of the token.
        :param sleep: Async sleep.
        :param max_concurrency: Concurrent requests allowed.
        """
        self._client = client
        self._token_env = token_env
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._root = str(client.base_url)

    async def get(
        self, url: str, params: QueryParams | None = None
    ) -> httpx.Response:
        """
        GET with retries.

        :param url: Path relative to the API root, or an absolute URL
            inside it.
        :param params: Query parameters.
        :returns: The 2xx response.
        :raises SourceError: See the module documentation.
        """
        reason = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with self._semaphore:
                    response = await self._client.get(url, params=params)
            except httpx.TransportError as exc:
                reason = f"{type(exc).__name__}: {exc}"
                delay = _backoff(attempt)
            else:
                if self._accept(response, url):
                    return response
                reason = f"HTTP {response.status_code}"
                delay = _retry_after(response)
                if delay is None:
                    delay = _backoff(attempt)
            if attempt < MAX_ATTEMPTS:
                logger.info(
                    "GitLab GET %s: %s; retry %d/%d in %.1fs",
                    url,
                    reason,
                    attempt,
                    MAX_ATTEMPTS - 1,
                    delay,
                )
                await self._sleep(delay)
        raise SourceUnavailableError(
            f"GitLab GET {url} failed after {MAX_ATTEMPTS} attempts: {reason}"
        )

    def _accept(self, response: httpx.Response, url: str) -> bool:
        """
        Classify a response.

        :param response: The response.
        :param url: Requested URL (for messages).
        :returns: ``True`` for 2xx, ``False`` if retryable.
        :raises SourceError: For any other status.
        """
        status = response.status_code
        if 200 <= status < 300:
            return True
        if _is_retryable(status):
            return False
        if status in (401, 403):
            raise SourceAccessError(
                f"GitLab refused access to {url} (HTTP {status}); check "
                f"the token in {self._token_env} and its permissions"
            )
        if status == 404:
            raise SourceNotFoundError(f"GitLab {url} not found (HTTP 404)")
        raise SourceError(f"GitLab GET {url} failed: HTTP {status}")

    async def get_json(
        self, url: str, params: QueryParams | None = None
    ) -> object:
        """
        GET and decode JSON.

        :param url: Path relative to the API root.
        :param params: Query parameters.
        :returns: The decoded body.
        :raises SourceError: On HTTP failure or invalid JSON.
        """
        response = await self.get(url, params)
        try:
            return response.json()
        except ValueError as exc:
            raise SourceUnavailableError(
                f"GitLab {url} returned invalid JSON"
            ) from exc

    async def get_pages(self, url: str, params: QueryParams) -> list[object]:
        """
        GET every page of a list endpoint.

        :param url: Path relative to the API root.
        :param params: Query parameters of the first page
            (``per_page`` is added).
        :returns: All items in page order.
        :raises SourceError: On any failure (no partial result).
        """
        first: dict[str, str | int] = {**params, "per_page": PER_PAGE}
        target: str = url
        query: QueryParams | None = first
        items: list[object] = []
        for _ in range(MAX_PAGES):
            response = await self.get(target, query)
            page = self._decode_page(response, url)
            items.extend(page)
            link = self._next_link(response, url)
            next_page = response.headers.get("X-Next-Page", "").strip()
            if link is not None:
                target, query = link, None
            elif next_page:
                target, query = url, {**first, "page": next_page}
            else:
                return items
        raise SourceUnavailableError(
            f"GitLab {url} returned more than {MAX_PAGES} pages"
        )

    @staticmethod
    def _decode_page(response: httpx.Response, url: str) -> list[object]:
        """
        Decode one page of a list endpoint.

        :param response: The response.
        :param url: Listing path (for messages).
        :returns: The page items.
        :raises SourceUnavailableError: If the body is not a JSON list.
        """
        try:
            page = response.json()
        except ValueError as exc:
            raise SourceUnavailableError(
                f"GitLab {url} returned invalid JSON"
            ) from exc
        if not isinstance(page, list):
            raise SourceUnavailableError(
                f"unexpected GitLab response for {url}"
            )
        return list(page)

    def _next_link(self, response: httpx.Response, url: str) -> str | None:
        """
        Read the ``Link: <...>; rel="next"`` target.

        :param response: The response.
        :param url: Listing path (for messages).
        :returns: The absolute next URL, or ``None``.
        :raises SourceUnavailableError: If it leaves the API root.
        """
        target = response.links.get("next", {}).get("url")
        if not target:
            return None
        if not target.startswith(self._root):
            raise SourceUnavailableError(
                f"GitLab {url} returned a next-page link outside the "
                "configured base_url; refusing to follow it"
            )
        return target
