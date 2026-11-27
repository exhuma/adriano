"""
The OIDC sign-in and sign-out flow of the Backend-for-Frontend.

Sign-in (Authorization Code with PKCE ``S256``, ``state`` and
``nonce``):

1. :meth:`LoginService.begin` creates a random ``state``, ``nonce``
   and PKCE verifier, stores them (encrypted, with the return path and
   redirect URI) in a **pending sign-in row** keyed by SHA-256 of the
   state, valid for 10 minutes, and returns the authorization URL. The
   router binds the state to the browser with the
   ``__Host-adriano-login`` cookie.
2. :meth:`LoginService.complete` requires the callback's ``state`` to
   equal the binding cookie, then **deletes** the row in its own
   committed transaction before anything else happens (``DELETE ...
   RETURNING``), so a state works exactly once even when the rest
   fails. It exchanges the code with the client secret, validates the
   ID token (``iss``, ``aud`` = client id, ``nonce``, ``exp``) and the
   access token (:class:`~app.auth.oidc.OidcValidator`: audience,
   issuer, roles claim) and creates the session.

Why a row and not only a signed cookie: a cookie cannot be made
single-use (the same cookie and callback URL could be replayed until
the cookie expires); the row can, and the PKCE verifier never leaves
the server.

Sign-out (:func:`end_session`): delete the session, revoke its refresh
token (best effort) and build the IdP's RP-initiated logout URL.

Every failure of :meth:`LoginService.complete` raises
:class:`LoginFailedError`; no session is created then.

Public API: :data:`LOGIN_TTL`, :func:`safe_return_to`,
:class:`LoginFailedError`, :class:`LoginStart`,
:class:`CompletedLogin`, :class:`LoginService`, :func:`end_session`.
"""

import base64
import datetime
import hashlib
import hmac
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.auth.cipher import CipherError, SessionCipher
from app.auth.idp import IdpClient, IdpGrantError, TokenSet
from app.errors import AdrianoError, AuthenticationError, AuthUnavailableError
from app.services.auth_sessions import SessionService
from app.services.session_values import SessionTokens, access_expiry, utc_now
from app.storage.session_port import (
    PendingLogin,
    SessionKind,
    SessionStoreProvider,
)

__all__ = [
    "LOGIN_TTL",
    "CompletedLogin",
    "LoginFailedError",
    "LoginService",
    "LoginStart",
    "end_session",
    "safe_return_to",
]

#: How long a started sign-in may take.
LOGIN_TTL = datetime.timedelta(minutes=10)

#: Longest accepted return path.
_MAX_RETURN_TO = 2048

logger = logging.getLogger(__name__)


def safe_return_to(value: str | None) -> str:
    """
    Accept only a same-site relative path as the post-sign-in target.

    :param value: The requested path.
    :returns: *value* when it starts with a single ``/`` and holds no
        backslash or control character; otherwise ``/``.
    """
    if (
        not value
        or len(value) > _MAX_RETURN_TO
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)
    ):
        return "/"
    return value


def _digest(value: str) -> str:
    """
    Hash a secret value for storage.

    :param value: The value.
    :returns: Its hex SHA-256.
    """
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _challenge(verifier: str) -> str:
    """
    Compute the PKCE ``S256`` challenge.

    :param verifier: The code verifier.
    :returns: Unpadded base64url of its SHA-256.
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class LoginFailedError(AdrianoError):
    """A sign-in callback that cannot complete (answered with HTTP 400)."""


@dataclass(frozen=True, slots=True)
class LoginStart:
    """
    A started sign-in.

    :param authorize_url: Where to send the browser.
    :param state: The state to bind to the browser.
    """

    authorize_url: str
    state: str


@dataclass(frozen=True, slots=True)
class CompletedLogin:
    """
    A completed sign-in.

    :param cookie: The new session's cookie value.
    :param return_to: The validated path to continue at.
    """

    cookie: str
    return_to: str


@dataclass(frozen=True, slots=True)
class _Pending:
    """
    Decrypted pending sign-in.

    :param verifier: PKCE verifier.
    :param nonce: Nonce.
    :param return_to: Return path.
    :param redirect_uri: Redirect URI of the authorization request.
    """

    verifier: str
    nonce: str
    return_to: str
    redirect_uri: str


class LoginService:
    """
    Start and complete OIDC sign-ins.

    :param provider: Session storage (pending sign-ins).
    :param cipher: Encryption of the pending sign-in data.
    :param idp: The IdP client.
    :param sessions: Creates the session on success.
    :param clock: Time source (tests).
    """

    def __init__(
        self,
        provider: SessionStoreProvider,
        cipher: SessionCipher,
        idp: IdpClient,
        sessions: SessionService,
        *,
        clock: Callable[[], datetime.datetime] = utc_now,
    ) -> None:
        """
        Store the collaborators.

        :param provider: Session storage.
        :param cipher: Encryption.
        :param idp: The IdP client.
        :param sessions: The session service.
        :param clock: Time source.
        """
        self._provider = provider
        self._cipher = cipher
        self._idp = idp
        self._sessions = sessions
        self._clock = clock

    def begin(self, *, return_to: str, redirect_uri: str) -> LoginStart:
        """
        Start a sign-in.

        :param return_to: Validated return path (:func:`safe_return_to`).
        :param redirect_uri: This app's ``/auth/callback`` URL.
        :returns: The authorization URL and the state.
        :raises AuthUnavailableError: If the IdP cannot be reached.
        """
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        url = self._idp.authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            nonce=nonce,
            code_challenge=_challenge(verifier),
        )
        payload = self._cipher.encrypt_json(
            {
                "verifier": verifier,
                "nonce": nonce,
                "return_to": return_to,
                "redirect_uri": redirect_uri,
            }
        )
        now = self._clock()
        with self._provider.unit_of_work() as store:
            store.purge_expired(now)
            store.insert_login(
                PendingLogin(
                    id=_digest(state),
                    payload=payload,
                    expires_at=now + LOGIN_TTL,
                )
            )
        return LoginStart(authorize_url=url, state=state)

    def _take(self, state: str) -> _Pending:
        """
        Consume the pending sign-in of *state* (single use).

        :param state: The callback's state.
        :returns: The decrypted pending sign-in.
        :raises LoginFailedError: If it is unknown, used or expired.
        """
        with self._provider.unit_of_work() as store:
            login = store.take_login(_digest(state))
        if login is None or login.expires_at <= self._clock():
            raise LoginFailedError(
                "this sign-in link is unknown, expired or was already used"
            )
        try:
            data: dict[str, Any] = self._cipher.decrypt_json(login.payload)
            return _Pending(
                verifier=str(data["verifier"]),
                nonce=str(data["nonce"]),
                return_to=safe_return_to(str(data["return_to"])),
                redirect_uri=str(data["redirect_uri"]),
            )
        except (CipherError, KeyError) as exc:
            raise LoginFailedError("this sign-in cannot be resumed") from exc

    def complete(
        self,
        *,
        code: str | None,
        state: str | None,
        bound_state: str | None,
        error: str | None = None,
    ) -> CompletedLogin:
        """
        Complete a sign-in from the callback parameters.

        :param code: The ``code`` query parameter.
        :param state: The ``state`` query parameter.
        :param bound_state: The browser's sign-in binding cookie.
        :param error: The ``error`` query parameter of a refused
            authorization.
        :returns: The new session's cookie and the return path.
        :raises LoginFailedError: On any failure (no session created).
        """
        if (
            not state
            or not bound_state
            or not hmac.compare_digest(state.encode(), bound_state.encode())
        ):
            raise LoginFailedError(
                "this sign-in was not started in this browser; start again"
            )
        pending = self._take(state)
        if error is not None or not code:
            raise LoginFailedError(
                "the identity provider did not complete the sign-in"
                + (f" ({error})" if error else "")
            )
        try:
            tokens = self._idp.exchange_code(
                code=code,
                code_verifier=pending.verifier,
                redirect_uri=pending.redirect_uri,
            )
            session = self._validated(tokens, pending.nonce)
        except (
            IdpGrantError,
            AuthenticationError,
            AuthUnavailableError,
        ) as exc:
            logger.warning("OIDC sign-in failed: %s", exc)
            raise LoginFailedError(
                "the sign-in could not be completed; start again"
            ) from exc
        claims, session_tokens = session
        cookie = self._sessions.create(SessionKind.OIDC, claims, session_tokens)
        return CompletedLogin(cookie=cookie, return_to=pending.return_to)

    def _validated(
        self, tokens: TokenSet, nonce: str
    ) -> tuple[dict[str, Any], SessionTokens]:
        """
        Validate the tokens of a code exchange.

        :param tokens: The tokens of the code exchange.
        :param nonce: The sign-in's nonce.
        :returns: The access-token claims and the session tokens.
        :raises AuthenticationError: If a token is missing or invalid.
        :raises AuthUnavailableError: If the IdP cannot be reached.
        """
        if not tokens.id_token:
            raise AuthenticationError(
                "the token response has no ID token", code="invalid_token"
            )
        identity = self._idp.validate_id_token(tokens.id_token, nonce=nonce)
        claims = self._idp.validate_access_token(tokens.access_token)
        if identity.get("sub") != claims.get("sub"):
            raise AuthenticationError(
                "ID token and access token name different subjects",
                code="invalid_token",
            )
        return claims, SessionTokens(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            id_token=tokens.id_token,
            access_expires_at=access_expiry(claims),
        )


def end_session(
    sessions: SessionService | None,
    idp: IdpClient | None,
    cookie: str | None,
    *,
    post_logout_redirect_uri: str,
) -> str | None:
    """
    Sign out: delete the session, revoke its refresh token.

    :param sessions: The session service (``None`` when sessions are
        not configured).
    :param idp: The IdP client (``None`` without OIDC).
    :param cookie: The session cookie value, if any.
    :param post_logout_redirect_uri: Where the IdP should send the
        browser after its own logout.
    :returns: The IdP's end-session URL for an OIDC session, else
        ``None``.
    """
    if sessions is None or cookie is None:
        return None
    ended = sessions.end(cookie)
    if ended is None or ended.kind is not SessionKind.OIDC or idp is None:
        return None
    if ended.refresh_token is not None:
        idp.revoke(ended.refresh_token)
    return idp.end_session_url(
        id_token=ended.id_token,
        post_logout_redirect_uri=post_logout_redirect_uri,
    )
