"""Application configuration loaded from the environment.

All runtime configuration is sourced from a single
``pydantic-settings`` :class:`Settings` class. Every environment
variable is prefixed with ``ADRIANO_`` to avoid collisions with other
services, and the settings object is instantiated once per process
through :func:`get_settings`.
"""

from functools import lru_cache

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings sourced from the environment.

    :cvar database_url: Plain ``postgresql://`` DSN for the
        application database, validated at startup. The SQLAlchemy
        ``+psycopg`` dialect modifier is injected at runtime, never
        stored here.
    :cvar test_database_url: DSN used only by the test suite.
    :cvar config_file: Path to the ``catalog.yaml`` source and policy
        configuration file.
    :cvar oidc_authority: OIDC discovery authority base URL.
    :cvar oidc_issuer: Expected JWT ``iss`` claim.
    :cvar oidc_audience: Expected JWT ``aud`` claim.
    :cvar oidc_roles_claim: Dotted path to the roles claim in the
        validated token payload.
    :cvar dev_auth_enabled: Whether the dev-only HS256 auth bypass is
        mounted. Must be ``False`` in production.
    :cvar dev_shared_secret: Shared secret for the dev-only auth
        bypass. Has no default; must be explicitly configured.
    """

    model_config = SettingsConfigDict(
        env_prefix="ADRIANO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: PostgresDsn = PostgresDsn(
        "postgresql://adriano:adriano@localhost:55432/adriano"
    )
    test_database_url: PostgresDsn = PostgresDsn(
        "postgresql://adriano:adriano@localhost:55432/adriano_test"
    )
    config_file: str = "catalog.yaml"

    oidc_authority: str | None = None
    oidc_issuer: str | None = None
    oidc_audience: str = "adr_viewer"
    oidc_roles_claim: str = "roles"

    dev_auth_enabled: bool = False
    dev_shared_secret: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached :class:`Settings` instance.

    :returns: The lazily constructed, memoised settings object.
    """
    return Settings()
