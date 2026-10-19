"""
Request and response models for identity, dev tokens and poll triggers.

- :class:`MeOut` -- ``GET /api/v1/me``.
- :class:`DevTokenIn` / :class:`DevTokenOut` -- ``POST /auth/dev/token``
  (mounted only when dev auth is enabled).
- :class:`PollAcceptedOut` -- ``POST /api/v1/sources/poll`` and
  ``POST /api/v1/sources/{id}/poll``.
"""

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


class DevTokenIn(BaseModel):
    """Identity to put into a dev token."""

    model_config = ConfigDict(extra="forbid")

    sub: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    roles: list[str] = Field(default_factory=list, max_length=50)


class DevTokenOut(BaseModel):
    """A minted dev access token (OAuth 2 token-response shape)."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class PollAcceptedOut(BaseModel):
    """An accepted background poll."""

    accepted: list[str]
    message: str
