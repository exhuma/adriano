"""
Request and response models for identity, sessions and poll triggers.

- :class:`MeOut` -- ``GET /api/v1/me``.
- :class:`SessionOut` -- ``GET /auth/session``.
- :class:`LogoutOut` -- ``POST /auth/logout``.
- :class:`DevLoginIn` -- ``POST /auth/dev/login`` (mounted only when
  dev auth is enabled).
- :class:`DevRoleOut` / :class:`DevRolesOut` -- ``GET /auth/dev/roles``
  (mounted only when dev auth is enabled).
- :class:`PollAcceptedOut` -- ``POST /api/v1/sources/poll`` and
  ``POST /api/v1/sources/{id}/poll``.
"""

import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.auth.rbac import Permission


class ReviewerOut(BaseModel):
    """Whether the caller may record approval decisions, and why."""

    model_config = ConfigDict(from_attributes=True)

    eligible: bool
    reason: str


class MeOut(BaseModel):
    """The authenticated caller and what they may do."""

    issuer: str
    subject: str
    display: str
    email: str | None
    roles: list[str]
    permissions: list[Permission]
    reviewer: ReviewerOut


class SessionOut(BaseModel):
    """Whether the browser has a usable session, and until when."""

    authenticated: bool
    expires_at: datetime.datetime | None = Field(
        default=None,
        description="When the session ends without further activity "
        "(never after its absolute expiry); omitted when not "
        "authenticated.",
    )


class LogoutOut(BaseModel):
    """Where to send the browser to end the IdP session too."""

    end_session_url: str | None


class DevLoginIn(BaseModel):
    """Identity of a dev session."""

    model_config = ConfigDict(extra="forbid")

    sub: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    roles: list[str] = Field(default_factory=list, max_length=50)


class DevRoleOut(BaseModel):
    """One ``rbac`` role of the loaded catalog and what it grants."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    permissions: list[Permission]


class DevRolesOut(BaseModel):
    """Role names of the loaded catalog, for dev sign-in presets."""

    model_config = ConfigDict(from_attributes=True)

    roles: list[DevRoleOut]
    reviewer_roles: list[str]


class PollAcceptedOut(BaseModel):
    """An accepted background poll."""

    accepted: list[str]
    message: str
