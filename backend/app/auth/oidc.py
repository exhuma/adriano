"""
RS256 bearer-token validation against the configured OIDC provider.

The backend is a stateless resource server (``module-auth-oidc``): it
never takes part in the login flow. :class:`OidcValidator` resolves the
JWKS URI from the provider's discovery document
(``<authority>/.well-known/openid-configuration``) **lazily**, on the
first token it validates -- never at import or startup, so an
unreachable IdP never stops the application. The resulting
:class:`jwt.PyJWKClient` is cached (it caches the key set and refetches
on an unknown ``kid``). A failed discovery is not cached; the next
request retries.

Validation: signature (RS256 only), ``exp``, ``nbf`` (when present),
``aud`` (``ADRIANO_OIDC_AUDIENCE``), ``iss`` (``ADRIANO_OIDC_ISSUER``,
or the discovery document's ``issuer`` when unset); ``exp``, ``iss``,
``aud`` and ``sub`` are required. No custom crypto: PyJWT does all of it.

Both the discovery request and the JWKS fetch use the shared outbound
TLS context of :mod:`app.tls` (``ADRIANO_TLS_VERIFY``,
``ADRIANO_EXTRA_CA_CERTS``).

Failures: an unacceptable token raises
:class:`~app.errors.AuthenticationError` (HTTP 401); an unreachable or
broken discovery document or JWKS endpoint raises
:class:`~app.errors.AuthUnavailableError` (HTTP 503). Token values are
never logged or echoed.

Public API: :data:`REQUIRED_CLAIMS`, :class:`OidcValidator`,
:func:`cached_oidc_validator`.
"""

import logging
import ssl
import threading
from collections.abc import Callable
from functools import lru_cache, partial
from pathlib import Path
from typing import Any

import httpx
import jwt

from app.errors import AuthenticationError, AuthUnavailableError
from app.tls import outbound_ssl_context

__all__ = ["REQUIRED_CLAIMS", "OidcValidator", "cached_oidc_validator"]

#: Claims every accepted token (real or dev) must carry.
REQUIRED_CLAIMS = ("exp", "iss", "aud", "sub")

_DISCOVERY_PATH = "/.well-known/openid-configuration"
_TIMEOUT_SECONDS = 10.0

logger = logging.getLogger(__name__)

type JwksClientFactory = Callable[[str], jwt.PyJWKClient]


def _default_jwks_client(
    uri: str, *, ssl_context: ssl.SSLContext | None = None
) -> jwt.PyJWKClient:
    """
    Build the production JWKS client.

    :param uri: JWKS URI from the discovery document.
    :param ssl_context: TLS context of the request; ``None`` uses the
        default outbound context (:func:`app.tls.outbound_ssl_context`).
    :returns: A caching :class:`jwt.PyJWKClient`.
    """
    return jwt.PyJWKClient(
        uri,
        timeout=_TIMEOUT_SECONDS,
        ssl_context=ssl_context or outbound_ssl_context(),
    )


def _invalid(message: str) -> AuthenticationError:
    """
    Build the 401 error for an unacceptable token.

    :param message: Readable reason (no token content).
    :returns: The error.
    """
    return AuthenticationError(message, code="invalid_token")


def _unavailable() -> AuthUnavailableError:
    """
    Build the 503 error for an unreachable identity provider.

    :returns: The error.
    """
    return AuthUnavailableError(
        "the identity provider is unavailable; try again later",
        code="auth_unavailable",
    )


class OidcValidator:
    """
    Validates RS256 tokens issued by one OIDC provider.

    :param authority: Discovery base URL (``ADRIANO_OIDC_AUTHORITY``).
    :param issuer: Expected ``iss``; ``None`` uses the discovery
        document's ``issuer``.
    :param audience: Expected ``aud``.
    :param transport: Optional httpx transport for the discovery
        request (tests inject a mock).
    :param jwks_client_factory: Builds the JWKS client from the URI
        (tests inject one serving local keys); ``None`` uses the
        production client.
    :param ssl_context: TLS context of the discovery and JWKS requests
        (see :mod:`app.tls`); ``None`` uses the default outbound
        context.
    """

    def __init__(
        self,
        authority: str,
        issuer: str | None,
        audience: str,
        *,
        transport: httpx.BaseTransport | None = None,
        jwks_client_factory: JwksClientFactory | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        """
        Store the settings; performs no I/O.

        :param authority: Discovery base URL.
        :param issuer: Expected ``iss``, or ``None``.
        :param audience: Expected ``aud``.
        :param transport: Optional httpx transport.
        :param jwks_client_factory: JWKS client factory, or ``None``.
        :param ssl_context: TLS context, or ``None`` for the default.
        """
        self._authority = authority.rstrip("/")
        self._issuer = issuer
        self._audience = audience
        self._transport = transport
        self._ssl_context = ssl_context or outbound_ssl_context()
        self._jwks_client_factory = jwks_client_factory or partial(
            _default_jwks_client, ssl_context=self._ssl_context
        )
        self._lock = threading.Lock()
        self._jwks: jwt.PyJWKClient | None = None
        self._resolved_issuer: str | None = issuer

    def _fetch_discovery(self) -> dict[str, Any]:
        """
        Fetch the discovery document.

        :returns: The parsed document.
        :raises AuthUnavailableError: If it cannot be fetched or parsed.
        """
        url = self._authority + _DISCOVERY_PATH
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=_TIMEOUT_SECONDS,
                follow_redirects=False,
                verify=self._ssl_context,
            ) as client:
                document = client.get(url).raise_for_status().json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "OIDC discovery %s failed: %s", url, type(exc).__name__
            )
            raise _unavailable() from exc
        if not isinstance(document, dict):
            logger.warning("OIDC discovery %s: not a JSON object", url)
            raise _unavailable()
        return document

    def _jwks_client(self) -> jwt.PyJWKClient:
        """
        Return the cached JWKS client, running discovery on first use.

        :returns: The JWKS client.
        :raises AuthUnavailableError: If discovery fails.
        """
        with self._lock:
            if self._jwks is not None:
                return self._jwks
            document = self._fetch_discovery()
            jwks_uri = document.get("jwks_uri")
            issuer = document.get("issuer")
            if not isinstance(jwks_uri, str) or (
                self._issuer is None and not isinstance(issuer, str)
            ):
                logger.warning(
                    "OIDC discovery for %s lacks jwks_uri or issuer",
                    self._authority,
                )
                raise _unavailable()
            try:
                self._jwks = self._jwks_client_factory(jwks_uri)
            except jwt.PyJWKClientError as exc:
                logger.warning("OIDC jwks_uri rejected: %s", exc)
                raise _unavailable() from exc
            if self._issuer is None:
                self._resolved_issuer = str(issuer)
            return self._jwks

    def _signing_key(self, token: str) -> jwt.PyJWK:
        """
        Find the signing key for a token by its ``kid``.

        :param token: Raw token.
        :returns: The key.
        :raises AuthenticationError: If no key matches.
        :raises AuthUnavailableError: If the JWKS cannot be fetched.
        """
        client = self._jwks_client()
        try:
            return client.get_signing_key_from_jwt(token)
        except jwt.PyJWKClientConnectionError as exc:
            logger.warning("OIDC JWKS fetch failed: %s", type(exc).__name__)
            raise _unavailable() from exc
        except (jwt.PyJWKClientError, jwt.InvalidTokenError) as exc:
            raise _invalid("token signing key is not known") from exc

    def decode(self, token: str) -> dict[str, Any]:
        """
        Validate an RS256 token and return its claims.

        :param token: Raw bearer token.
        :returns: The verified claims.
        :raises AuthenticationError: If the token is not acceptable.
        :raises AuthUnavailableError: If the IdP cannot be reached.
        """
        key = self._signing_key(token)
        try:
            return jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._resolved_issuer,
                options={"require": list(REQUIRED_CLAIMS)},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError(
                "token has expired", code="token_expired"
            ) from exc
        except jwt.InvalidTokenError as exc:
            raise _invalid(f"token rejected ({type(exc).__name__})") from exc


@lru_cache(maxsize=4)
def cached_oidc_validator(
    authority: str,
    issuer: str | None,
    audience: str,
    tls_verify: bool = True,
    extra_ca_certs: tuple[Path, ...] = (),
) -> OidcValidator:
    """
    Return the process-wide validator for one provider configuration.

    Caching keeps the discovery result and the JWKS cache across
    requests. The TLS settings are part of the key as plain values;
    the context comes from :func:`app.tls.outbound_ssl_context`.

    :param authority: Discovery base URL.
    :param issuer: Expected ``iss``, or ``None``.
    :param audience: Expected ``aud``.
    :param tls_verify: Whether to verify the provider's certificate
        (``ADRIANO_TLS_VERIFY``).
    :param extra_ca_certs: Extra trusted CA paths
        (``ADRIANO_EXTRA_CA_CERTS``).
    :returns: The shared validator.
    :raises app.errors.ConfigurationError: If an extra CA path cannot
        be loaded.
    """
    return OidcValidator(
        authority,
        issuer,
        audience,
        ssl_context=outbound_ssl_context(tls_verify, extra_ca_certs),
    )
