"""
Tests for :class:`app.services.auth_sessions.SessionService`.

Against the test database (real ``auth_session`` rows), with an
injected clock where time matters and :class:`tests.auth_helpers.FakeIdp`
for refreshes.
"""

import datetime
import io
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.auth.cipher import SessionCipher
from app.cli import main
from app.config import Settings
from app.errors import AuthenticationError
from app.services.auth_sessions import (
    SessionPolicy,
    SessionService,
    SessionTokens,
    purge_expired_sessions,
)
from app.storage.postgres.sessions import PostgresSessionStoreProvider
from app.storage.session_port import SessionKind
from tests.auth_helpers import TEST_SESSION_KEY, FakeIdp

T0 = datetime.datetime(2026, 10, 22, 12, 0, tzinfo=datetime.UTC)
POLICY = SessionPolicy(
    idle=datetime.timedelta(minutes=30), max_age=datetime.timedelta(hours=2)
)
OTHER_KEY = "hPbuVOp5vq3Kt6QZbGVfC0sZ8m0tZ8bE3dzGq4vXg2Q="
CLAIMS = {"iss": "adriano-dev", "sub": "alice"}


class Clock:
    """A settable time source."""

    def __init__(self) -> None:
        """Start at :data:`T0`."""
        self.now = T0

    def __call__(self) -> datetime.datetime:
        """
        Read the time.

        :returns: The current fake time.
        """
        return self.now


@pytest.fixture
def sessions_provider(engine: Engine) -> PostgresSessionStoreProvider:
    """
    Build the session storage over the clean test database.

    :param engine: Clean engine.
    :returns: The provider.
    """
    return PostgresSessionStoreProvider(engine)


def _service(
    provider: PostgresSessionStoreProvider,
    clock: Clock,
    *,
    key: str = TEST_SESSION_KEY,
    accepted: tuple[SessionKind, ...] = (SessionKind.DEV, SessionKind.OIDC),
    idp: FakeIdp | None = None,
) -> SessionService:
    """
    Build a session service.

    :param provider: Session storage.
    :param clock: Time source.
    :param key: Session key.
    :param accepted: Accepted kinds.
    :param idp: Fake IdP for refreshes.
    :returns: The service.
    """
    client = idp.idp_client(idp.validator()) if idp else None
    return SessionService(
        provider,
        SessionCipher(SecretStr(key)),
        POLICY,
        accepted=accepted,
        idp=client,
        clock=clock,
    )


def _count(engine: Engine) -> int:
    """
    Count the session rows.

    :param engine: Test database engine.
    :returns: The count.
    """
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT count(*) FROM auth_session")
        ).scalar_one()


def test_idle_expiry_slides_but_never_passes_the_absolute(
    sessions_provider: PostgresSessionStoreProvider,
) -> None:
    """Ensure activity extends the idle expiry up to the absolute one."""
    clock = Clock()
    service = _service(sessions_provider, clock)
    cookie = service.create(SessionKind.DEV, CLAIMS)
    expiries = []

    for _ in range(4):
        clock.now += datetime.timedelta(minutes=25)
        expiries.append(service.authenticate(cookie).expires_at)

    assert expiries[0] == T0 + datetime.timedelta(minutes=55)
    assert expiries[-1] == T0 + POLICY.max_age
    clock.now = T0 + POLICY.max_age
    with pytest.raises(AuthenticationError):
        service.authenticate(cookie)


def test_idle_session_ends(
    sessions_provider: PostgresSessionStoreProvider, engine: Engine
) -> None:
    """Ensure a session unused for the idle time is gone."""
    clock = Clock()
    service = _service(sessions_provider, clock)
    cookie = service.create(SessionKind.DEV, CLAIMS)
    clock.now += POLICY.idle

    with pytest.raises(AuthenticationError):
        service.authenticate(cookie)

    assert _count(engine) == 0


def test_changed_session_key_ends_the_session(
    sessions_provider: PostgresSessionStoreProvider, engine: Engine
) -> None:
    """Ensure a session encrypted under an old key is a 401, deleted."""
    clock = Clock()
    cookie = _service(sessions_provider, clock).create(SessionKind.DEV, CLAIMS)
    rotated = _service(sessions_provider, clock, key=OTHER_KEY)

    assert rotated.peek(cookie) is None
    with pytest.raises(AuthenticationError):
        rotated.authenticate(cookie)
    assert _count(engine) == 0


def test_oidc_session_without_refresh_token_ends_at_expiry(
    sessions_provider: PostgresSessionStoreProvider, engine: Engine
) -> None:
    """Ensure an expiring session that cannot refresh is a 401."""
    clock = Clock()
    idp = FakeIdp()
    service = _service(sessions_provider, clock, idp=idp)
    tokens = SessionTokens(
        access_token="a",
        refresh_token=None,
        id_token=None,
        access_expires_at=T0 + datetime.timedelta(seconds=30),
    )
    cookie = service.create(SessionKind.OIDC, CLAIMS, tokens)

    with pytest.raises(AuthenticationError):
        service.authenticate(cookie)

    assert idp.refresh_calls == 0
    assert _count(engine) == 0


def test_purge_removes_only_expired_rows(
    sessions_provider: PostgresSessionStoreProvider, engine: Engine
) -> None:
    """Ensure the purge deletes expired sessions and keeps live ones."""
    clock = Clock()
    service = _service(sessions_provider, clock)
    service.create(SessionKind.DEV, CLAIMS)
    clock.now += POLICY.idle
    live = service.create(SessionKind.DEV, CLAIMS)  # purges the first

    purged = purge_expired_sessions(sessions_provider, clock.now)

    assert purged == 0
    assert _count(engine) == 1
    assert service.peek(live) is not None


def test_poll_command_purges_expired_sessions(
    sessions_provider: PostgresSessionStoreProvider,
    engine: Engine,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    """Ensure ``adriano poll`` deletes expired sessions."""
    clock = Clock()
    clock.now = datetime.datetime.now(datetime.UTC) - datetime.timedelta(1)
    _service(sessions_provider, clock).create(SessionKind.DEV, CLAIMS)
    config = tmp_path / "catalog.yaml"
    config.write_text("sources: []\n", encoding="utf-8")
    settings = test_settings.model_copy(update={"config_file": str(config)})

    code = main(["poll"], settings=settings, out=io.StringIO())

    assert code == 0
    assert _count(engine) == 0


def test_database_refuses_idle_expiry_after_absolute(
    sessions_provider: PostgresSessionStoreProvider, engine: Engine
) -> None:
    """Ensure the schema itself keeps idle expiry within the absolute."""
    _service(sessions_provider, Clock()).create(SessionKind.DEV, CLAIMS)

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE auth_session SET idle_expires_at = "
                "absolute_expires_at + interval '1 second'"
            )
        )
