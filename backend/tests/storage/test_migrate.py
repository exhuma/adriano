"""
Tests for the locked migration and the ``migrate``/``serve`` commands.

They run against the test database. Each test that changes the schema
leaves it at head, so the session-wide ``migrated_engine`` of the other
storage tests stays valid.
"""

import io
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, func, select, text

from alembic import command
from app import cli
from app.config import Settings
from app.storage.postgres.migrations import (
    MIGRATION_LOCK_KEY,
    alembic_ini_path,
    upgrade_to_head,
)
from tests.storage.conftest import (
    BACKEND_DIR,
    alembic_config,
    database_url_for_tests,
    make_engine,
)

#: Upper bound for waiting on database state; never a fixed sleep.
DEADLINE_SECONDS = 30


def _head() -> str:
    """
    Return the head revision of the migration scripts.

    :returns: The revision id.
    """
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    assert head is not None
    return head


def _current(engine: Engine) -> str | None:
    """
    Read the applied revision.

    :param engine: Engine bound to the test database.
    :returns: The revision, ``None`` without an ``alembic_version`` row.
    """
    with engine.connect() as connection:
        exists = connection.execute(
            text("SELECT to_regclass('alembic_version')")
        ).scalar()
        if exists is None:
            return None
        return connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()


@pytest.fixture
def base_engine() -> Iterator[Engine]:
    """
    Provide the test database downgraded to base, upgraded afterwards.

    :returns: An engine bound to the empty test database.
    """
    config = alembic_config()
    command.downgrade(config, "base")
    engine = make_engine()
    yield engine
    command.upgrade(config, "head")
    engine.dispose()


def test_alembic_ini_is_found_next_to_the_package() -> None:
    """Ensure alembic.ini resolves to the backend directory."""
    assert alembic_ini_path() == BACKEND_DIR / "alembic.ini"


def test_upgrade_to_head_applies_the_migrations(base_engine: Engine) -> None:
    """Ensure the locked upgrade brings an empty database to head."""
    upgrade_to_head(database_url_for_tests())

    assert _current(base_engine) == _head()


def test_upgrade_to_head_releases_the_lock(base_engine: Engine) -> None:
    """Ensure no migration lock is left behind after the upgrade."""
    upgrade_to_head(database_url_for_tests())

    with base_engine.connect() as connection:
        acquired = connection.execute(
            select(func.pg_try_advisory_lock(MIGRATION_LOCK_KEY))
        ).scalar()
        connection.execute(select(func.pg_advisory_unlock(MIGRATION_LOCK_KEY)))
    assert acquired is True


def _waiting_on_lock(engine: Engine) -> int:
    """
    Count sessions waiting for the migration lock.

    :param engine: Engine bound to the test database.
    :returns: The number of ungranted advisory locks on the key.
    """
    high, low = divmod(MIGRATION_LOCK_KEY, 1 << 32)
    with engine.connect() as connection:
        return connection.execute(
            text(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                "AND NOT granted AND classid = :high AND objid = :low "
                "AND objsubid = 1"
            ),
            {"high": high, "low": low},
        ).scalar_one()


def _start_migrate(tmp_path: Path) -> subprocess.Popen[bytes]:
    """
    Start ``adriano migrate`` in a separate process.

    :param tmp_path: Working directory without a ``.env``.
    :returns: The running process.
    """
    env = {**os.environ, "ADRIANO_DATABASE_URL": database_url_for_tests()}
    return subprocess.Popen(
        [sys.executable, "-c", "from app.cli import run; run()", "migrate"],
        cwd=tmp_path,
        env={**env, "PYTHONPATH": str(BACKEND_DIR)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def test_concurrent_migrate_processes_both_succeed(
    base_engine: Engine, tmp_path: Path
) -> None:
    """Ensure two concurrent `adriano migrate` runs serialise and pass."""
    with base_engine.connect() as holder:
        holder.execute(select(func.pg_advisory_lock(MIGRATION_LOCK_KEY)))
        holder.commit()
        processes = [_start_migrate(tmp_path) for _ in range(2)]
        deadline = time.monotonic() + DEADLINE_SECONDS
        while _waiting_on_lock(base_engine) < 2:
            assert time.monotonic() < deadline, "migrations never waited"
            time.sleep(0.05)
        holder.execute(select(func.pg_advisory_unlock(MIGRATION_LOCK_KEY)))
        holder.commit()

    outputs = [p.communicate(timeout=DEADLINE_SECONDS)[0] for p in processes]

    assert [p.returncode for p in processes] == [0, 0], outputs
    assert _current(base_engine) == _head()


def test_migrate_command_reports_an_unreachable_database(
    test_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ensure `adriano migrate` exits 2 with a hint on a dead database."""
    settings = test_settings.model_copy(
        update={"database_url": "postgresql://a:b@localhost:1/none"}
    )

    code = cli.main(["migrate"], settings=settings, out=io.StringIO())

    assert code == cli.EXIT_USAGE
    assert "ADRIANO_DATABASE_URL" in capsys.readouterr().err


@pytest.fixture
def exec_calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """
    Record ``adriano serve``'s exec instead of replacing the process.

    :param monkeypatch: Pytest monkeypatch.
    :returns: The recorded argument vectors.
    """
    calls: list[list[str]] = []
    monkeypatch.setattr(cli, "_exec", calls.append)
    return calls


def test_serve_migrates_then_execs_uvicorn(
    test_settings: Settings,
    base_engine: Engine,
    exec_calls: list[list[str]],
) -> None:
    """Ensure `adriano serve` migrates first, then starts Uvicorn."""
    settings = test_settings.model_copy(update={"workers": 3})

    code = cli.main(["serve"], settings=settings, out=io.StringIO())

    assert code == cli.EXIT_OK
    assert _current(base_engine) == _head()
    assert exec_calls == [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--workers",
            "3",
        ]
    ]


def test_serve_skips_migration_when_disabled(
    test_settings: Settings,
    base_engine: Engine,
    exec_calls: list[list[str]],
) -> None:
    """Ensure ADRIANO_MIGRATE_ON_START=false leaves the schema alone."""
    settings = test_settings.model_copy(update={"migrate_on_start": False})

    cli.main(["serve"], settings=settings, out=io.StringIO())

    assert _current(base_engine) is None
    assert len(exec_calls) == 1


def test_serve_passes_trusted_proxies(
    test_settings: Settings, exec_calls: list[list[str]]
) -> None:
    """Ensure ADRIANO_FORWARDED_ALLOW_IPS reaches Uvicorn."""
    settings = test_settings.model_copy(
        update={"migrate_on_start": False, "forwarded_allow_ips": "10.0.0.0/8"}
    )

    cli.main(["serve"], settings=settings, out=io.StringIO())

    assert exec_calls[0][-2:] == ["--forwarded-allow-ips", "10.0.0.0/8"]


def test_serve_does_not_start_when_migration_fails(
    test_settings: Settings, exec_calls: list[list[str]]
) -> None:
    """Ensure a failed migration stops `adriano serve` with exit code 2."""
    settings = test_settings.model_copy(
        update={"database_url": "postgresql://a:b@localhost:1/none"}
    )

    code = cli.main(["serve"], settings=settings, out=io.StringIO())

    assert code == cli.EXIT_USAGE
    assert exec_calls == []
