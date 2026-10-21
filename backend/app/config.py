"""Application configuration loaded from the environment.

All runtime configuration is sourced from a single
``pydantic-settings`` :class:`Settings` class. Every environment
variable is prefixed with ``ADRIANO_`` to avoid collisions with other
services, and the settings object is instantiated once per process
through :func:`get_settings`.

Invalid configuration fails loudly: a missing or malformed
``ADRIANO_DATABASE_URL``, a malformed ``ADRIANO_OIDC_AUTHORITY`` or an
incomplete SPA OIDC configuration raises a ``ValidationError`` when the
settings are built, i.e. at process start.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Accepted ``ADRIANO_OIDC_AUTHORITY`` shape: scheme ``http``/``https``,
#: a DNS name or IPv4 host, an optional port and an optional plain
#: path. No query, fragment, userinfo, quotes or spaces: the origin is
#: written into the ``Content-Security-Policy`` header, where such
#: characters could inject directives.
_AUTHORITY_PATTERN = re.compile(
    r"https?://[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?"
    r"(:[0-9]{1,5})?"
    r"(/[A-Za-z0-9._~%/-]*)?",
    re.ASCII,
)


class Settings(BaseSettings):
    """Typed application settings sourced from the environment.

    :cvar database_url: Plain ``postgresql://`` DSN for the
        application database, validated at startup. Required: there is
        no default. The SQLAlchemy ``+psycopg`` dialect modifier is
        injected at runtime, never stored here.
    :cvar test_database_url: DSN used only by the test suite.
    :cvar config_file: Path to the ``catalog.yaml`` source and policy
        configuration file.
    :cvar oidc_authority: OIDC discovery authority base URL, shared by
        the backend (token validation) and the SPA (sign-in). Must be
        ``http(s)://host[:port][/path]``.
    :cvar oidc_issuer: Expected JWT ``iss`` claim.
    :cvar oidc_audience: Expected JWT ``aud`` claim.
    :cvar oidc_roles_claim: Dotted path to the roles claim in the
        validated token payload.
    :cvar oidc_client_id: Public OIDC client id the SPA signs in with
        (served in ``/config.js``).
    :cvar oidc_scope: OIDC scopes the SPA requests at sign-in.
    :cvar oidc_redirect_uri: Redirect URI for the SPA's authorization
        code callback; unset, the SPA uses ``<origin>/auth/callback``.
    :cvar oidc_post_logout_redirect_uri: Where the IdP sends the
        browser after sign-out; unset, the SPA uses its origin.
    :cvar dev_auth_enabled: Whether the dev-only HS256 auth bypass is
        mounted. Must be ``False`` in production.
    :cvar dev_shared_secret: Shared secret for the dev-only auth
        bypass. Has no default; must be explicitly configured.
    :cvar stale_after_minutes: Minutes after the last successful poll
        of a registration before its freshness is reported as
        ``stale`` (see ``GET /api/v1/sources`` and the record detail
        freshness field).
    :cvar static_dir: Directory holding the built SPA (``index.html``,
        ``assets/``). When set, the API process also serves the SPA and
        ``/config.js`` (see :mod:`app.web`); unset, it serves the API
        only.
    :cvar migrate_on_start: Whether ``adriano serve`` applies the
        database migrations (under an advisory lock) before starting
        the server.
    :cvar version: Application version reported by ``/healthz`` and
        the OpenAPI document; set from the image build.
    :cvar workers: Number of Uvicorn worker processes started by
        ``adriano serve``.
    :cvar forwarded_allow_ips: Comma-separated proxy addresses whose
        ``X-Forwarded-*`` headers Uvicorn trusts (``adriano serve``);
        unset keeps Uvicorn's default (``127.0.0.1``).
    """

    model_config = SettingsConfigDict(
        env_prefix="ADRIANO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: PostgresDsn
    test_database_url: PostgresDsn = PostgresDsn(
        "postgresql://adriano:adriano@localhost:55432/adriano_test"
    )
    config_file: str = "catalog.yaml"

    oidc_authority: str | None = None
    oidc_issuer: str | None = None
    oidc_audience: str = "adr_viewer"
    oidc_roles_claim: str = "roles"
    oidc_client_id: str | None = None
    oidc_scope: str = "openid profile email"
    oidc_redirect_uri: str | None = None
    oidc_post_logout_redirect_uri: str | None = None

    dev_auth_enabled: bool = False
    dev_shared_secret: str | None = None

    stale_after_minutes: int = 120

    static_dir: Path | None = None
    migrate_on_start: bool = True
    version: str = "dev"
    workers: int = Field(default=4, ge=1)
    forwarded_allow_ips: str | None = None

    @field_validator(
        "oidc_authority",
        "oidc_issuer",
        "oidc_client_id",
        "oidc_redirect_uri",
        "oidc_post_logout_redirect_uri",
        "dev_shared_secret",
        "static_dir",
        "forwarded_allow_ips",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        """
        Treat an empty or whitespace-only optional string as unset.

        ``docker compose`` passes ``${NAME:-}`` as an empty string, not
        as an absent variable. Without this, ``ADRIANO_OIDC_ISSUER=""``
        would be compared literally against the token's ``iss`` instead
        of falling back to the discovery document's issuer.

        :param value: The raw input value.
        :returns: ``None`` for a blank string, else *value* unchanged.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("oidc_authority")
    @classmethod
    def _check_authority(cls, value: str | None) -> str | None:
        """
        Reject an authority that is not ``http(s)://host[:port][/path]``.

        :param value: The authority, ``None`` when unset.
        :returns: *value* unchanged.
        :raises ValueError: If the authority has another shape.
        """
        if value is not None and not _AUTHORITY_PATTERN.fullmatch(value):
            raise ValueError(
                "ADRIANO_OIDC_AUTHORITY must look like "
                "https://host[:port][/path] (http or https; no query, "
                "fragment, credentials, quotes or spaces)"
            )
        return value

    @model_validator(mode="after")
    def _check_spa_oidc(self) -> Self:
        """
        Require the SPA's OIDC settings as a pair when serving the SPA.

        An authority without a client id (or the reverse) would serve a
        sign-in page that can never work.

        :returns: The settings unchanged.
        :raises ValueError: If exactly one of the two is set while
            ``static_dir`` is set.
        """
        if self.static_dir is None:
            return self
        if (self.oidc_authority is None) != (self.oidc_client_id is None):
            raise ValueError(
                "ADRIANO_OIDC_AUTHORITY and ADRIANO_OIDC_CLIENT_ID must "
                "be set together when ADRIANO_STATIC_DIR is set (the SPA "
                "needs both to sign in); set the missing one or unset "
                "both"
            )
        return self

    @property
    def oidc_origin(self) -> str | None:
        """
        The ``scheme://host[:port]`` origin of :attr:`oidc_authority`.

        :returns: The origin, ``None`` when no authority is set.
        """
        if self.oidc_authority is None:
            return None
        scheme, _, rest = self.oidc_authority.partition("://")
        return f"{scheme}://{rest.split('/', 1)[0]}"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached :class:`Settings` instance.

    :returns: The lazily constructed, memoised settings object.
    """
    return Settings()  # pyright: ignore[reportCallIssue]
