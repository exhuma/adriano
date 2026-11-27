"""
PostgreSQL implementation of :mod:`app.storage.session_port`.

Tables ``auth_session`` and ``auth_login`` (migration
``0004_auth_session``). All SQL uses bound parameters. The refresh lock
is ``SELECT ... FOR UPDATE`` on the session row, held until the unit
of work ends.

Public API: :class:`PostgresSessionStore`,
:class:`PostgresSessionStoreProvider`.
"""

import datetime
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, Update, delete, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.storage.postgres.models import AuthLoginRow, AuthSessionRow
from app.storage.session_port import (
    PendingLogin,
    SessionKind,
    SessionTokensUpdate,
    StoredSession,
)

__all__ = ["PostgresSessionStore", "PostgresSessionStoreProvider"]


def _stored(row: AuthSessionRow) -> StoredSession:
    """
    Convert a row to the port value.

    :param row: The ORM row.
    :returns: The value.
    """
    return StoredSession(
        id=row.id,
        kind=SessionKind(row.kind),
        subject=row.subject,
        claims=row.claims,
        access_token=row.access_token,
        refresh_token=row.refresh_token,
        id_token=row.id_token,
        access_expires_at=row.access_expires_at,
        created_at=row.created_at,
        last_seen_at=row.last_seen_at,
        idle_expires_at=row.idle_expires_at,
        absolute_expires_at=row.absolute_expires_at,
    )


class PostgresSessionStore:
    """
    :class:`~app.storage.session_port.SessionStore` bound to a session.

    :param session: The unit-of-work session (inside a transaction).
    """

    def __init__(self, session: Session) -> None:
        """:param session: The unit-of-work session."""
        self._session = session

    def insert_session(self, session: StoredSession) -> None:
        """
        Store a new session.

        :param session: The session.
        """
        self._session.add(
            AuthSessionRow(
                id=session.id,
                kind=session.kind.value,
                subject=session.subject,
                claims=session.claims,
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                id_token=session.id_token,
                access_expires_at=session.access_expires_at,
                created_at=session.created_at,
                last_seen_at=session.last_seen_at,
                idle_expires_at=session.idle_expires_at,
                absolute_expires_at=session.absolute_expires_at,
            )
        )
        self._session.flush()

    def get_session(
        self, session_id: str, *, lock: bool = False
    ) -> StoredSession | None:
        """
        Load a session, optionally locking its row.

        :param session_id: Session id.
        :param lock: ``SELECT ... FOR UPDATE``.
        :returns: The session, or ``None``.
        """
        query = select(AuthSessionRow).where(AuthSessionRow.id == session_id)
        if lock:
            query = query.with_for_update()
        query = query.execution_options(populate_existing=True)
        row = self._session.scalars(query).one_or_none()
        return None if row is None else _stored(row)

    def update_tokens(
        self, session_id: str, update: SessionTokensUpdate
    ) -> None:
        """
        Replace the tokens and claims of a session.

        :param session_id: Session id.
        :param update: The new values.
        """
        self._session.execute(
            _update_session(session_id).values(
                claims=update.claims,
                access_token=update.access_token,
                refresh_token=update.refresh_token,
                id_token=update.id_token,
                access_expires_at=update.access_expires_at,
            )
        )

    def touch_session(
        self,
        session_id: str,
        *,
        seen_at: datetime.datetime,
        idle_expires_at: datetime.datetime,
    ) -> None:
        """
        Record activity.

        :param session_id: Session id.
        :param seen_at: Activity time.
        :param idle_expires_at: New sliding expiry.
        """
        self._session.execute(
            _update_session(session_id).values(
                last_seen_at=seen_at, idle_expires_at=idle_expires_at
            )
        )

    def delete_session(self, session_id: str) -> StoredSession | None:
        """
        Delete a session.

        :param session_id: Session id.
        :returns: The deleted session, or ``None``.
        """
        row = self._session.scalars(
            delete(AuthSessionRow)
            .where(AuthSessionRow.id == session_id)
            .returning(AuthSessionRow)
        ).one_or_none()
        return None if row is None else _stored(row)

    def insert_login(self, login: PendingLogin) -> None:
        """
        Store a pending sign-in.

        :param login: The pending sign-in.
        """
        self._session.add(
            AuthLoginRow(
                id=login.id, payload=login.payload, expires_at=login.expires_at
            )
        )
        self._session.flush()

    def take_login(self, login_id: str) -> PendingLogin | None:
        """
        Delete and return a pending sign-in.

        :param login_id: Hex SHA-256 of the ``state``.
        :returns: The pending sign-in, or ``None``.
        """
        row = self._session.execute(
            delete(AuthLoginRow)
            .where(AuthLoginRow.id == login_id)
            .returning(
                AuthLoginRow.id, AuthLoginRow.payload, AuthLoginRow.expires_at
            )
        ).one_or_none()
        if row is None:
            return None
        return PendingLogin(
            id=row.id, payload=row.payload, expires_at=row.expires_at
        )

    def purge_expired(self, now: datetime.datetime) -> int:
        """
        Delete expired sessions and pending sign-ins.

        :param now: Current time.
        :returns: The number of deleted rows.
        """
        sessions = self._session.execute(
            delete(AuthSessionRow).where(
                or_(
                    AuthSessionRow.idle_expires_at <= now,
                    AuthSessionRow.absolute_expires_at <= now,
                )
            )
        )
        logins = self._session.execute(
            delete(AuthLoginRow).where(AuthLoginRow.expires_at <= now)
        )
        counts: list[int] = [
            sessions.rowcount,  # pyright: ignore[reportAttributeAccessIssue]
            logins.rowcount,  # pyright: ignore[reportAttributeAccessIssue]
        ]
        return sum(counts)


def _update_session(session_id: str) -> Update:
    """
    Start an ``UPDATE`` of one session row.

    :param session_id: Session id.
    :returns: The statement.
    """
    return update(AuthSessionRow).where(AuthSessionRow.id == session_id)


class PostgresSessionStoreProvider:
    """
    :class:`~app.storage.session_port.SessionStoreProvider` over an engine.

    :param engine: SQLAlchemy engine of the application database.
    """

    def __init__(self, engine: Engine) -> None:
        """:param engine: SQLAlchemy engine."""
        self._sessions = sessionmaker(
            bind=engine, autoflush=False, expire_on_commit=False
        )

    @contextmanager
    def unit_of_work(self) -> Iterator[PostgresSessionStore]:
        """
        Open one session and transaction.

        :returns: A context manager yielding the store; commits on
            normal exit, rolls back on error.
        """
        with self._sessions() as session, session.begin():
            yield PostgresSessionStore(session)
