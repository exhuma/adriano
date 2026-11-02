"""
Server-side sign-in sessions and pending sign-ins.

Hand-written. The backend became the OIDC client (Backend-for-Frontend,
ADR 0022): the browser holds only an opaque session cookie, and the
session lives here.

- ``auth_session``: one row per session. ``id`` is the hex SHA-256 of
  the cookie value (the raw value is never stored). ``claims`` and the
  three IdP tokens are Fernet tokens under ``ADRIANO_SESSION_KEY``; the
  tokens are NULL for dev sessions. ``idle_expires_at`` slides with
  activity but never past ``absolute_expires_at`` (checked).
- ``auth_login``: one row per pending sign-in, keyed by the hex SHA-256
  of its ``state`` and deleted when the callback consumes it (single
  use). ``payload`` (PKCE verifier, nonce, return path, redirect URI)
  is a Fernet token.

Expired rows of both tables are purged on sign-in and by
``adriano poll``; the ``*_expires_at`` indexes serve that purge.

Revision ID: 0004_auth_session
Revises: 0003_erratum_content
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_auth_session"
down_revision: str | Sequence[str] | None = "0003_erratum_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str, nullable: bool = False) -> sa.Column:
    """
    Build a ``timestamptz`` column without a default.

    :param name: Column name.
    :param nullable: Whether NULL is allowed.
    :returns: The column.
    """
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _create_auth_session() -> None:
    op.create_table(
        "auth_session",
        sa.Column("id", sa.Text),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("subject", sa.Text, nullable=False),
        sa.Column("claims", sa.Text, nullable=False),
        sa.Column("access_token", sa.Text),
        sa.Column("refresh_token", sa.Text),
        sa.Column("id_token", sa.Text),
        _timestamp("access_expires_at", nullable=True),
        _timestamp("created_at"),
        _timestamp("last_seen_at"),
        _timestamp("idle_expires_at"),
        _timestamp("absolute_expires_at"),
        sa.PrimaryKeyConstraint("id", name="pk_auth_session"),
        sa.CheckConstraint(
            "kind IN ('oidc', 'dev')", name="ck_auth_session_kind"
        ),
        sa.CheckConstraint(
            "idle_expires_at <= absolute_expires_at",
            name="ck_auth_session_idle_within_absolute",
        ),
        sa.CheckConstraint(
            "(kind = 'oidc' AND access_token IS NOT NULL "
            "AND access_expires_at IS NOT NULL) OR (kind = 'dev' "
            "AND access_token IS NULL AND refresh_token IS NULL "
            "AND id_token IS NULL AND access_expires_at IS NULL)",
            name="ck_auth_session_tokens",
        ),
    )
    op.create_index(
        "ix_auth_session_idle_expires_at", "auth_session", ["idle_expires_at"]
    )
    comments = {
        "TABLE auth_session": "Server-side sign-in sessions (BFF); the "
        "browser holds only the opaque cookie value.",
        "COLUMN auth_session.id": "Hex SHA-256 of the session cookie value; "
        "the raw value is never stored.",
        "COLUMN auth_session.kind": "oidc (IdP sign-in) or dev (dev login, "
        "accepted only while dev auth is enabled).",
        "COLUMN auth_session.subject": "sub of the signed-in user "
        "(plain text, for operators).",
        "COLUMN auth_session.claims": "Fernet token (ADRIANO_SESSION_KEY) of "
        "the validated access-token claims as JSON.",
        "COLUMN auth_session.access_token": "Fernet token of the IdP access "
        "token; NULL for dev sessions.",
        "COLUMN auth_session.refresh_token": "Fernet token of the current "
        "(rotated) refresh token; NULL for dev sessions or without one.",
        "COLUMN auth_session.id_token": "Fernet token of the ID token "
        "(id_token_hint at logout); NULL for dev sessions.",
        "COLUMN auth_session.idle_expires_at": "Sliding expiry, extended "
        "by activity; never after absolute_expires_at.",
        "COLUMN auth_session.absolute_expires_at": "Hard end of the "
        "session (sign-in time + ADRIANO_SESSION_MAX_HOURS).",
    }
    for target, text in comments.items():
        op.execute(f"COMMENT ON {target} IS '{text}'")


def _create_auth_login() -> None:
    op.create_table(
        "auth_login",
        sa.Column("id", sa.Text),
        sa.Column("payload", sa.Text, nullable=False),
        _timestamp("expires_at"),
        sa.PrimaryKeyConstraint("id", name="pk_auth_login"),
    )
    op.create_index("ix_auth_login_expires_at", "auth_login", ["expires_at"])
    op.execute(
        "COMMENT ON TABLE auth_login IS 'Pending OIDC sign-ins; a row is "
        "deleted when its callback consumes it (single-use state).'"
    )
    op.execute(
        "COMMENT ON COLUMN auth_login.id IS 'Hex SHA-256 of the sign-in state.'"
    )
    op.execute(
        "COMMENT ON COLUMN auth_login.payload IS 'Fernet token of the PKCE "
        "verifier, nonce, return path and redirect URI as JSON.'"
    )


def upgrade() -> None:
    """Create ``auth_session`` and ``auth_login``."""
    _create_auth_session()
    _create_auth_login()


def downgrade() -> None:
    """Drop both tables (every session ends)."""
    op.drop_table("auth_login")
    op.drop_table("auth_session")
