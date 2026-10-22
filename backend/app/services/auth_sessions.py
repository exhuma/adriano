"""
Server-side sign-in sessions (Backend-for-Frontend).

The browser holds only an opaque random cookie value (256 bits); the
session row is keyed by its SHA-256 and holds the claims and the IdP
tokens encrypted with :class:`~app.auth.cipher.SessionCipher`.

Lifetime (:class:`SessionPolicy`): a session ends after
``ADRIANO_SESSION_IDLE_MINUTES`` without activity or
``ADRIANO_SESSION_MAX_HOURS`` after sign-in, whichever comes first. The
idle expiry slides with activity but is never moved past the absolute
one. Activity is recorded at most once per :data:`TOUCH_INTERVAL`, so
most requests only read the row.

Inline refresh (OIDC sessions): when the stored access token expires
within :data:`REFRESH_MARGIN`, :meth:`SessionService.authenticate`
refreshes it at the IdP while holding a row lock (``SELECT ... FOR
UPDATE``), re-checking the expiry after taking the lock, so parallel
requests (other workers, other replicas) wait for one refresh and then
use its result: a rotated refresh token is never spent twice. The new
access token is validated with the
:class:`~app.auth.oidc.OidcValidator` before it is stored. A refused
refresh (``invalid_grant``) or a session without a refresh token ends
the session (HTTP 401); an unreachable IdP is HTTP 503 and keeps the
session.

Dev sessions hold claims only and are accepted only while dev auth is
active; OIDC sessions only while OIDC is configured.

Public API: :data:`REFRESH_MARGIN`, :data:`TOUCH_INTERVAL`,
:class:`SessionService`, :func:`purge_expired_sessions`, and the value
types of :mod:`app.services.session_values` (re-exported here).
"""

import dataclasses
import datetime
import logging
import secrets
from collections.abc import Callable, Collection, Mapping
from typing import Any

from app.auth.cipher import CipherError, SessionCipher
from app.auth.idp import IdpClient, IdpGrantError, TokenSet
from app.errors import AuthenticationError, AuthUnavailableError
from app.services.session_values import (
    ActiveSession,
    EndedSession,
    SessionPolicy,
    SessionTokens,
    access_expiry,
    session_id_for,
    utc_now,
)
from app.storage.session_port import (
    SessionKind,
    SessionStore,
    SessionStoreProvider,
    SessionTokensUpdate,
    StoredSession,
)

__all__ = [
    "REFRESH_MARGIN",
    "TOUCH_INTERVAL",
    "ActiveSession",
    "EndedSession",
    "SessionPolicy",
    "SessionService",
    "SessionTokens",
    "purge_expired_sessions",
    "session_id_for",
]

#: Refresh the access token when it expires within this margin.
REFRESH_MARGIN = datetime.timedelta(seconds=60)

#: Record activity (and slide the idle expiry) at most this often.
TOUCH_INTERVAL = datetime.timedelta(minutes=1)

logger = logging.getLogger(__name__)

_UNKNOWN = "the session is unknown or has ended; sign in again"

type Clock = Callable[[], datetime.datetime]


def purge_expired_sessions(
    provider: SessionStoreProvider, now: datetime.datetime | None = None
) -> int:
    """
    Delete expired sessions and pending sign-ins.

    :param provider: Session storage.
    :param now: Current time (default: now).
    :returns: The number of deleted rows.
    """
    with provider.unit_of_work() as store:
        return store.purge_expired(now or utc_now())


def _ended(message: str) -> AuthenticationError:
    """
    Build the 401 of a session that is unknown or has ended.

    :param message: Readable reason (no secrets).
    :returns: The error.
    """
    return AuthenticationError(
        message, code="session_expired", hint="sign in again"
    )


class SessionService:
    """
    Create, authenticate, refresh and end sessions.

    :param provider: Session storage.
    :param cipher: Encryption of the stored values.
    :param policy: Lifetimes.
    :param accepted: Session kinds currently accepted (dev only while
        dev auth is active, OIDC only while OIDC is configured).
    :param idp: The IdP client, for refreshes (``None`` without OIDC).
    :param clock: Time source (tests).
    """

    def __init__(
        self,
        provider: SessionStoreProvider,
        cipher: SessionCipher,
        policy: SessionPolicy,
        *,
        accepted: Collection[SessionKind],
        idp: IdpClient | None = None,
        clock: Clock = utc_now,
    ) -> None:
        """
        Store the collaborators.

        :param provider: Session storage.
        :param cipher: Encryption of the stored values.
        :param policy: Lifetimes.
        :param accepted: Accepted session kinds.
        :param idp: The IdP client, or ``None``.
        :param clock: Time source.
        """
        self._provider = provider
        self._cipher = cipher
        self._policy = policy
        self._accepted = frozenset(accepted)
        self._idp = idp
        self._clock = clock

    def create(
        self,
        kind: SessionKind,
        claims: Mapping[str, Any],
        tokens: SessionTokens | None = None,
    ) -> str:
        """
        Start a session; expired sessions are purged first.

        :param kind: Session kind.
        :param claims: Verified claims (``sub`` required).
        :param tokens: The IdP tokens (OIDC sessions only).
        :returns: The cookie value (never stored).
        """
        now = self._clock()
        cookie = secrets.token_urlsafe(32)
        absolute = now + self._policy.max_age
        session = StoredSession(
            id=session_id_for(cookie),
            kind=kind,
            subject=str(claims["sub"]),
            claims=self._cipher.encrypt_json(claims),
            access_token=None,
            refresh_token=None,
            id_token=None,
            access_expires_at=None,
            created_at=now,
            last_seen_at=now,
            idle_expires_at=min(now + self._policy.idle, absolute),
            absolute_expires_at=absolute,
        )
        if tokens is not None:
            session = dataclasses.replace(
                session,
                access_token=self._cipher.encrypt(tokens.access_token),
                refresh_token=self._seal(tokens.refresh_token),
                id_token=self._seal(tokens.id_token),
                access_expires_at=tokens.access_expires_at,
            )
        with self._provider.unit_of_work() as store:
            purged = store.purge_expired(now)
            store.insert_session(session)
        if purged:
            logger.info("purged %d expired session row(s)", purged)
        return cookie

    def _seal(self, value: str | None) -> str | None:
        """
        Encrypt an optional value.

        :param value: Plain value, or ``None``.
        :returns: The encrypted value, or ``None``.
        """
        return None if value is None else self._cipher.encrypt(value)

    def _rejection(
        self, stored: StoredSession, now: datetime.datetime
    ) -> str | None:
        """
        Explain why a stored session cannot be used.

        :param stored: The session.
        :param now: Current time.
        :returns: The reason, or ``None`` when it is usable.
        """
        if stored.idle_expires_at <= now or stored.absolute_expires_at <= now:
            return "the session has expired; sign in again"
        if stored.kind not in self._accepted:
            return f"{stored.kind} sessions are not accepted; sign in again"
        return None

    def _active(self, stored: StoredSession) -> ActiveSession:
        """
        Decrypt a usable session.

        :param stored: The session.
        :returns: The active session.
        :raises CipherError: If it was encrypted under another key.
        """
        return ActiveSession(
            kind=stored.kind,
            claims=self._cipher.decrypt_json(stored.claims),
            expires_at=stored.idle_expires_at,
        )

    def peek(self, cookie: str) -> ActiveSession | None:
        """
        Look a session up without refreshing or touching it.

        :param cookie: The cookie value.
        :returns: The session, or ``None`` when it is not usable.
        """
        with self._provider.unit_of_work() as store:
            stored = store.get_session(session_id_for(cookie))
        if stored is None or self._rejection(stored, self._clock()):
            return None
        try:
            return self._active(stored)
        except CipherError:
            return None

    def _touch(
        self, store: SessionStore, stored: StoredSession, now: datetime.datetime
    ) -> StoredSession:
        """
        Record activity when the last record is old enough.

        :param store: Store in the current unit of work.
        :param stored: The usable session.
        :param now: Current time.
        :returns: The session as stored afterwards.
        """
        if now - stored.last_seen_at < TOUCH_INTERVAL:
            return stored
        idle = min(now + self._policy.idle, stored.absolute_expires_at)
        store.touch_session(stored.id, seen_at=now, idle_expires_at=idle)
        return dataclasses.replace(
            stored, last_seen_at=now, idle_expires_at=idle
        )

    def _load(self, session_id: str, now: datetime.datetime) -> StoredSession:
        """
        Load and touch a session, deleting it when it is not usable.

        :param session_id: Session id.
        :param now: Current time.
        :returns: The usable session.
        :raises AuthenticationError: If it is not usable (HTTP 401).
        """
        with self._provider.unit_of_work() as store:
            stored = store.get_session(session_id)
            if stored is None:
                raise _ended(_UNKNOWN)
            reason = self._rejection(stored, now)
            if reason is None:
                return self._touch(store, stored, now)
            store.delete_session(session_id)
        raise _ended(reason)

    def _needs_refresh(
        self, stored: StoredSession, now: datetime.datetime
    ) -> bool:
        """
        Tell whether the access token must be refreshed now.

        :param stored: The session.
        :param now: Current time.
        :returns: ``True`` for an OIDC session close to expiry.
        """
        expires = stored.access_expires_at
        return expires is not None and expires - now < REFRESH_MARGIN

    def authenticate(self, cookie: str) -> ActiveSession:
        """
        Resolve a cookie to a usable session, refreshing it if needed.

        :param cookie: The cookie value.
        :returns: The active session.
        :raises AuthenticationError: If the session is unknown, expired,
            not accepted or cannot be refreshed (HTTP 401; the row is
            deleted).
        :raises AuthUnavailableError: If the IdP cannot be reached for
            a refresh (HTTP 503; the session is kept).
        """
        session_id = session_id_for(cookie)
        now = self._clock()
        stored = self._load(session_id, now)
        if self._needs_refresh(stored, now):
            stored = self._refresh(session_id)
        try:
            return self._active(stored)
        except CipherError:
            self.end(cookie)
            raise _ended("the session cannot be read; sign in again") from None

    def _refresh(self, session_id: str) -> StoredSession:
        """
        Refresh a session's tokens under its row lock.

        :param session_id: Session id.
        :returns: The session with fresh tokens.
        :raises AuthenticationError: If the session ended meanwhile or
            the refresh was refused (the row is deleted).
        :raises AuthUnavailableError: If the IdP cannot be reached.
        """
        with self._provider.unit_of_work() as store:
            locked = store.get_session(session_id, lock=True)
            if locked is None:
                raise _ended(_UNKNOWN)
            now = self._clock()
            reason = self._rejection(locked, now)
            if reason is None:
                if not self._needs_refresh(locked, now):
                    return locked  # another request refreshed it
                refreshed = self._refreshed(locked)
                if refreshed is not None:
                    store.update_tokens(session_id, refreshed)
                    return dataclasses.replace(
                        locked,
                        claims=refreshed.claims,
                        access_token=refreshed.access_token,
                        refresh_token=refreshed.refresh_token,
                        id_token=refreshed.id_token,
                        access_expires_at=refreshed.access_expires_at,
                    )
                reason = "the session could not be renewed; sign in again"
            store.delete_session(session_id)
        raise _ended(reason)

    def _refreshed(self, stored: StoredSession) -> SessionTokensUpdate | None:
        """
        Call the IdP for new tokens and validate them.

        :param stored: The locked session.
        :returns: The encrypted update, or ``None`` when the session
            must end (no refresh token, grant refused, invalid token).
        :raises AuthUnavailableError: If the IdP cannot be reached or
            answers with another error.
        """
        if self._idp is None or stored.refresh_token is None:
            return None
        try:
            refresh_token = self._cipher.decrypt(stored.refresh_token)
            tokens = self._idp.refresh(refresh_token)
            claims = self._idp.validate_access_token(tokens.access_token)
        except CipherError, AuthenticationError:
            return None
        except IdpGrantError as exc:
            if exc.error == "invalid_grant":
                return None
            logger.warning("OIDC refresh refused: %s", exc.error)
            raise AuthUnavailableError(
                "the identity provider refused to renew the session; try "
                "again later",
                code="auth_unavailable",
            ) from exc
        return self._update(stored, tokens, claims, refresh_token)

    def _update(
        self,
        stored: StoredSession,
        tokens: TokenSet,
        claims: Mapping[str, Any],
        previous_refresh: str,
    ) -> SessionTokensUpdate:
        """
        Encrypt refreshed tokens, keeping what the IdP did not resend.

        :param stored: The locked session.
        :param tokens: The new tokens.
        :param claims: Verified claims of the new access token.
        :param previous_refresh: The refresh token just used (plain).
        :returns: The update.
        """
        return SessionTokensUpdate(
            claims=self._cipher.encrypt_json(claims),
            access_token=self._cipher.encrypt(tokens.access_token),
            refresh_token=self._cipher.encrypt(
                tokens.refresh_token or previous_refresh
            ),
            id_token=self._seal(tokens.id_token) or stored.id_token,
            access_expires_at=access_expiry(claims),
        )

    def end(self, cookie: str) -> EndedSession | None:
        """
        Delete a session (logout).

        :param cookie: The cookie value.
        :returns: Its tokens for revocation and logout, or ``None`` if
            there was no such session.
        """
        with self._provider.unit_of_work() as store:
            stored = store.delete_session(session_id_for(cookie))
        if stored is None:
            return None
        return EndedSession(
            kind=stored.kind,
            refresh_token=self._open(stored.refresh_token),
            id_token=self._open(stored.id_token),
        )

    def _open(self, value: str | None) -> str | None:
        """
        Decrypt an optional value, tolerating a changed key.

        :param value: Encrypted value, or ``None``.
        :returns: The plain value, or ``None``.
        """
        if value is None:
            return None
        try:
            return self._cipher.decrypt(value)
        except CipherError:
            return None
