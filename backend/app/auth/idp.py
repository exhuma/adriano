"""
The backend as a confidential OIDC client (Backend-for-Frontend).

:class:`IdpClient` talks to the IdP's endpoints from the discovery
document that :class:`~app.auth.oidc.OidcValidator` fetches and caches:

- the ``authorization_endpoint`` URL of a sign-in (Authorization Code
  with PKCE ``S256``, ``state`` and ``nonce``);
- the ``token_endpoint``: code exchange and refresh. The client
  authenticates with ``client_secret_basic`` (RFC 6749 §2.3.1: id and
  secret form-encoded, then Basic), or with ``client_secret_post`` when
  the discovery document lists only that;
- the ``revocation_endpoint`` (RFC 7009, best effort) and the
  ``end_session_endpoint`` URL (RP-initiated logout).

Every request uses the shared outbound TLS context of :mod:`app.tls`
and never follows redirects. Tokens and the client secret are never
logged.

Failures: the token endpoint refusing a grant (HTTP 400/401 with an
OAuth ``error``) raises :class:`IdpGrantError`; an unreachable or
broken IdP raises :class:`~app.errors.AuthUnavailableError` (HTTP
503).

Public API: :class:`TokenSet`, :class:`IdpGrantError`,
:class:`IdpClient`.
"""

import base64
import logging
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from pydantic import SecretStr

from app.auth.oidc import OidcValidator
from app.errors import AuthUnavailableError

__all__ = ["IdpClient", "IdpGrantError", "TokenSet"]

_TIMEOUT_SECONDS = 10.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TokenSet:
    """
    Tokens from one token-endpoint response.

    :param access_token: The access token.
    :param refresh_token: The refresh token, if the IdP issued one.
    :param id_token: The ID token, if the IdP issued one.
    """

    access_token: str
    refresh_token: str | None
    id_token: str | None


class IdpGrantError(Exception):
    """
    The token endpoint refused the grant (HTTP 400/401).

    :param error: The OAuth ``error`` code (``invalid_grant`` ...), or
        ``http_<status>`` when the response carried none.
    """

    def __init__(self, error: str) -> None:
        """
        Store the error code.

        :param error: The OAuth error code.
        """
        super().__init__(f"the identity provider refused the grant: {error}")
        self.error = error


def _unavailable() -> AuthUnavailableError:
    """
    Build the 503 error for an unreachable identity provider.

    :returns: The error.
    """
    return AuthUnavailableError(
        "the identity provider is unavailable; try again later",
        code="auth_unavailable",
    )


def _optional_text(body: Mapping[str, Any], key: str) -> str | None:
    """
    Read a non-empty string member.

    :param body: Parsed JSON object.
    :param key: Member name.
    :returns: The value, or ``None``.
    """
    value = body.get(key)
    return value if isinstance(value, str) and value else None


def _with_query(url: str, params: Mapping[str, str]) -> str:
    """
    Append query parameters to an endpoint URL.

    :param url: Endpoint URL (may already carry a query).
    :param params: Parameters to add.
    :returns: The URL.
    """
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(params)}"


class IdpClient:
    """
    Confidential-client calls to one OIDC provider.

    :param validator: Validator of the same provider; supplies the
        discovery document and validates the tokens received.
    :param client_id: This client's id.
    :param client_secret: This client's secret.
    :param scope: Scopes requested at sign-in.
    :param transport: Optional httpx transport (tests inject a mock).
    :param ssl_context: TLS context (see :mod:`app.tls`).
    """

    def __init__(
        self,
        validator: OidcValidator,
        *,
        client_id: str,
        client_secret: SecretStr,
        scope: str,
        transport: httpx.BaseTransport | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        """
        Store the client settings; performs no I/O.

        :param validator: Validator of the same provider.
        :param client_id: Client id.
        :param client_secret: Client secret.
        :param scope: Requested scopes.
        :param transport: Optional httpx transport.
        :param ssl_context: TLS context, or ``None`` for httpx's default
            (tests only; production passes the shared context).
        """
        self._validator = validator
        self.client_id = client_id
        self._secret = client_secret
        self._scope = scope
        self._transport = transport
        self._ssl_context = ssl_context

    @property
    def validator(self) -> OidcValidator:
        """
        The provider's token validator.

        :returns: The validator.
        """
        return self._validator

    def _endpoint(self, name: str) -> str | None:
        """
        Read an endpoint URL from the discovery document.

        :param name: Discovery member (``token_endpoint`` ...).
        :returns: The URL, or ``None`` when the IdP does not offer it.
        :raises AuthUnavailableError: If discovery fails.
        """
        return _optional_text(self._validator.discovery(), name)

    def _required_endpoint(self, name: str) -> str:
        """
        Read an endpoint every sign-in needs.

        :param name: Discovery member.
        :returns: The URL.
        :raises AuthUnavailableError: If discovery fails or lacks it.
        """
        url = self._endpoint(name)
        if url is None:
            logger.warning("OIDC discovery lacks %s", name)
            raise _unavailable()
        return url

    def authorization_url(
        self, *, redirect_uri: str, state: str, nonce: str, code_challenge: str
    ) -> str:
        """
        Build the authorization request URL.

        :param redirect_uri: This app's ``/auth/callback`` URL.
        :param state: Single-use sign-in state.
        :param nonce: Value the ID token must echo.
        :param code_challenge: PKCE ``S256`` challenge.
        :returns: The URL to redirect the browser to.
        :raises AuthUnavailableError: If discovery fails.
        """
        return _with_query(
            self._required_endpoint("authorization_endpoint"),
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "scope": self._scope,
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )

    def _uses_post_auth(self) -> bool:
        """
        Tell whether the IdP supports only ``client_secret_post``.

        :returns: ``True`` to send the credentials in the form body.
        """
        methods = self._validator.discovery().get(
            "token_endpoint_auth_methods_supported"
        )
        if not isinstance(methods, list):
            return False
        return (
            "client_secret_basic" not in methods
            and "client_secret_post" in methods
        )

    def _authenticated(
        self, form: dict[str, str]
    ) -> tuple[dict[str, str], dict[str, str]]:
        """
        Add the client authentication to a token-endpoint request.

        :param form: The form fields.
        :returns: The form and the extra headers.
        """
        secret = self._secret.get_secret_value()
        if self._uses_post_auth():
            return {
                **form,
                "client_id": self.client_id,
                "client_secret": secret,
            }, {}
        pair = f"{quote(self.client_id, safe='')}:{quote(secret, safe='')}"
        encoded = base64.b64encode(pair.encode()).decode("ascii")
        return form, {"Authorization": f"Basic {encoded}"}

    def _post(self, url: str, form: dict[str, str]) -> httpx.Response:
        """
        POST an authenticated form.

        :param url: Endpoint URL.
        :param form: Form fields (without client authentication).
        :returns: The response.
        :raises AuthUnavailableError: If the IdP cannot be reached.
        """
        data, headers = self._authenticated(form)
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=_TIMEOUT_SECONDS,
                follow_redirects=False,
                verify=self._ssl_context or True,
            ) as client:
                return client.post(url, data=data, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("OIDC request failed: %s", type(exc).__name__)
            raise _unavailable() from exc

    def _token_request(self, form: dict[str, str]) -> TokenSet:
        """
        Call the token endpoint.

        :param form: Grant fields.
        :returns: The tokens.
        :raises IdpGrantError: If the IdP refuses the grant.
        :raises AuthUnavailableError: If the IdP cannot be reached or
            answers unexpectedly.
        """
        response = self._post(self._required_endpoint("token_endpoint"), form)
        try:
            body: object = response.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        fields: dict[str, Any] = body  # pyright: ignore[reportUnknownVariableType]
        if response.status_code in (400, 401):
            error = _optional_text(fields, "error")
            raise IdpGrantError(error or f"http_{response.status_code}")
        access_token = _optional_text(fields, "access_token")
        if response.status_code != 200 or access_token is None:
            logger.warning(
                "OIDC token endpoint answered HTTP %d", response.status_code
            )
            raise _unavailable()
        return TokenSet(
            access_token=access_token,
            refresh_token=_optional_text(fields, "refresh_token"),
            id_token=_optional_text(fields, "id_token"),
        )

    def exchange_code(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> TokenSet:
        """
        Exchange an authorization code.

        :param code: The code from the callback.
        :param code_verifier: The PKCE verifier of the sign-in.
        :param redirect_uri: The redirect URI of the authorization
            request.
        :returns: The tokens.
        :raises IdpGrantError: If the IdP refuses the code.
        :raises AuthUnavailableError: If the IdP cannot be reached.
        """
        return self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            }
        )

    def refresh(self, refresh_token: str) -> TokenSet:
        """
        Refresh the tokens of a session.

        :param refresh_token: The current refresh token.
        :returns: The new tokens (``refresh_token`` is the rotated one,
            ``None`` if the IdP does not rotate).
        :raises IdpGrantError: If the IdP refuses the refresh token.
        :raises AuthUnavailableError: If the IdP cannot be reached.
        """
        return self._token_request(
            {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )

    def validate_access_token(self, token: str) -> dict[str, Any]:
        """
        Validate an access token (see :meth:`OidcValidator.decode`).

        :param token: The access token.
        :returns: Its verified claims.
        :raises app.errors.AuthenticationError: If it is not acceptable.
        :raises AuthUnavailableError: If the IdP cannot be reached.
        """
        return self._validator.decode(token)

    def validate_id_token(self, token: str, *, nonce: str) -> dict[str, Any]:
        """
        Validate an ID token for this client.

        :param token: The ID token.
        :param nonce: The sign-in's nonce.
        :returns: Its verified claims.
        :raises app.errors.AuthenticationError: If it is not acceptable.
        :raises AuthUnavailableError: If the IdP cannot be reached.
        """
        return self._validator.decode_id_token(
            token, client_id=self.client_id, nonce=nonce
        )

    def revoke(self, refresh_token: str) -> bool:
        """
        Revoke a refresh token, if the IdP offers revocation.

        Best effort: failures are logged and swallowed.

        :param refresh_token: The token.
        :returns: Whether the IdP accepted the revocation.
        """
        try:
            url = self._endpoint("revocation_endpoint")
            if url is None:
                return False
            response = self._post(
                url,
                {"token": refresh_token, "token_type_hint": "refresh_token"},
            )
        except AuthUnavailableError:
            return False
        if response.status_code != 200:
            logger.warning(
                "OIDC revocation answered HTTP %d", response.status_code
            )
            return False
        return True

    def end_session_url(
        self, *, id_token: str | None, post_logout_redirect_uri: str
    ) -> str | None:
        """
        Build the RP-initiated logout URL.

        :param id_token: The session's ID token (``id_token_hint``).
        :param post_logout_redirect_uri: Where the IdP sends the browser
            afterwards.
        :returns: The URL, or ``None`` when the IdP has no
            ``end_session_endpoint`` or cannot be reached.
        """
        try:
            url = self._endpoint("end_session_endpoint")
        except AuthUnavailableError:
            return None
        if url is None:
            return None
        params = {
            "client_id": self.client_id,
            "post_logout_redirect_uri": post_logout_redirect_uri,
        }
        if id_token:
            params = {"id_token_hint": id_token, **params}
        return _with_query(url, params)
