"""Application configuration loaded from the environment.

All runtime configuration is sourced from a single
``pydantic-settings`` :class:`Settings` class. Every environment
variable is prefixed with ``ADRIANO_`` to avoid collisions with other
services, and the settings object is instantiated once per process
through :func:`get_settings`.

Invalid configuration fails loudly: a missing or malformed
``ADRIANO_DATABASE_URL``, a malformed ``ADRIANO_OIDC_AUTHORITY`` or
``ADRIANO_SESSION_KEY``, an incomplete OIDC client configuration or dev
auth without a session key raises a ``ValidationError`` when the
settings are built, i.e. at process start.
"""

import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self

from cryptography.fernet import Fernet
from pydantic import (
    Field,
    PostgresDsn,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: Accepted ``ADRIANO_OIDC_AUTHORITY`` shape: scheme ``http``/``https``,
#: a DNS name or IPv4 host, an optional port and an optional plain
#: path. No query, fragment, userinfo, quotes or spaces, so the
#: discovery URL built from it is unambiguous.
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
    :cvar oidc_authority: OIDC discovery authority base URL. Setting
        it enables sign-in through the backend (a confidential client)
        and requires :attr:`oidc_client_id`,
        :attr:`oidc_client_secret` and :attr:`session_key`. Must be
        ``http(s)://host[:port][/path]``.
    :cvar oidc_issuer: Expected JWT ``iss`` claim.
    :cvar oidc_audience: Expected ``aud`` claim of access tokens.
    :cvar oidc_roles_claim: Dotted path to the roles claim in the
        validated access token payload.
    :cvar oidc_client_id: Client id of the backend at the IdP; also
        the expected ``aud`` of ID tokens.
    :cvar oidc_client_secret: Client secret of the backend at the IdP
        (confidential client). Never logged or served.
    :cvar oidc_scope: Scopes requested at sign-in. ``offline_access``
        asks for a refresh token, which keeps the session usable after
        the first access token expires.
    :cvar dev_auth_enabled: Whether the dev-only login
        (``POST /auth/dev/login``) is mounted. Must be ``False`` in
        production; requires :attr:`session_key`.
    :cvar dev_shared_secret: Second, independent switch of the dev
        login: the dev routes are mounted only when it is set as well.
        Has no default; must be unset in production.
    :cvar session_key: Fernet key encrypting the server-side sessions
        (claims and IdP tokens) at rest. Required when OIDC or dev auth
        is enabled. Generate one with ``python -c "from
        cryptography.fernet import Fernet;
        print(Fernet.generate_key().decode())"``.
    :cvar session_idle_minutes: A session ends after this many minutes
        without a request.
    :cvar session_max_hours: A session ends this many hours after
        sign-in, however active it is.
    :cvar stale_after_minutes: Minutes after the last successful poll
        of a registration before its freshness is reported as
        ``stale`` (see ``GET /api/v1/sources`` and the record detail
        freshness field).
    :cvar static_dir: Directory holding the built SPA (``index.html``,
        ``assets/``). When set, the API process also serves the SPA and
        ``/config.js`` (see :mod:`app.web`); unset, it serves the API
        only.
    :cvar tls_verify: Whether outbound HTTPS calls (OIDC discovery,
        the JWKS endpoint, network sources such as GitLab) verify the
        server certificate.
        ``False`` disables verification entirely; meant only as a
        stop-gap for non-production instances behind an internal CA.
    :cvar extra_ca_certs: PEM files (bundles allowed) and directories
        (their ``*.pem`` and ``*.crt`` files) whose certificates
        outbound HTTPS trusts in addition to the standard set, e.g. an
        internal CA. Comma-separated in the environment; every path
        must exist. Unset (or blank) trusts the standard set only.
        Ignored when ``tls_verify`` is ``False``. Loaded by
        :mod:`app.tls`.
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
    oidc_client_secret: SecretStr | None = None
    oidc_scope: str = "openid profile email offline_access"

    dev_auth_enabled: bool = False
    dev_shared_secret: str | None = None

    session_key: SecretStr | None = None
    session_idle_minutes: int = Field(default=480, ge=1)
    session_max_hours: int = Field(default=24, ge=1)

    stale_after_minutes: int = 120

    static_dir: Path | None = None
    migrate_on_start: bool = True
    tls_verify: bool = True
    extra_ca_certs: Annotated[tuple[Path, ...] | None, NoDecode] = None
    version: str = "dev"
    workers: int = Field(default=4, ge=1)
    forwarded_allow_ips: str | None = None

    @field_validator(
        "oidc_authority",
        "oidc_issuer",
        "oidc_client_id",
        "oidc_client_secret",
        "dev_shared_secret",
        "session_key",
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

    @field_validator("extra_ca_certs", mode="before")
    @classmethod
    def _split_paths(cls, value: object) -> object:
        """
        Split a comma-separated path list; blank means unset.

        :param value: The raw input: a string from the environment, or
            an iterable of paths.
        :returns: A tuple of the non-blank entries, ``None`` when there
            are none, or *value* unchanged when it is of another type.
        """
        if isinstance(value, str):
            value = value.split(",")
        if not isinstance(value, Iterable):
            return value
        entries = tuple(str(item).strip() for item in value)
        paths = tuple(Path(entry) for entry in entries if entry)
        return paths or None

    @field_validator("extra_ca_certs")
    @classmethod
    def _check_paths_exist(
        cls, value: tuple[Path, ...] | None
    ) -> tuple[Path, ...] | None:
        """
        Reject an extra CA path that does not exist.

        The files themselves are parsed later, by :mod:`app.tls`.

        :param value: The paths, ``None`` when unset.
        :returns: *value* unchanged.
        :raises ValueError: If a path does not exist.
        """
        missing = [str(path) for path in value or () if not path.exists()]
        if missing:
            raise ValueError(
                "ADRIANO_EXTRA_CA_CERTS: no such file or directory: "
                + ", ".join(missing)
            )
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

    @field_validator("session_key")
    @classmethod
    def _check_session_key(cls, value: SecretStr | None) -> SecretStr | None:
        """
        Reject a session key that is not a Fernet key.

        :param value: The key, ``None`` when unset.
        :returns: *value* unchanged.
        :raises ValueError: If it is not 32 url-safe base64 bytes.
        """
        if value is None:
            return value
        try:
            Fernet(value.get_secret_value().encode("ascii"))
        except ValueError, UnicodeEncodeError:
            raise ValueError(
                "ADRIANO_SESSION_KEY must be a Fernet key (32 url-safe "
                "base64-encoded bytes); generate one with "
                "Fernet.generate_key()"
            ) from None
        return value

    def _missing_auth_settings(self) -> list[str]:
        """
        List the settings the enabled sign-in mechanisms still need.

        :returns: Environment variable names, empty when complete.
        """
        missing: list[str] = []
        if self.oidc_authority is not None:
            if self.oidc_client_id is None:
                missing.append("ADRIANO_OIDC_CLIENT_ID")
            if self.oidc_client_secret is None:
                missing.append("ADRIANO_OIDC_CLIENT_SECRET")
        enabled = self.oidc_authority is not None or self.dev_auth_enabled
        if enabled and self.session_key is None:
            missing.append("ADRIANO_SESSION_KEY")
        return missing

    @model_validator(mode="after")
    def _check_auth(self) -> Self:
        """
        Require the client credentials and the session key.

        OIDC sign-in needs the client id and secret (the backend is a
        confidential client) and the session key; the dev login needs
        the session key.

        :returns: The settings unchanged.
        :raises ValueError: Naming every missing setting.
        """
        missing = self._missing_auth_settings()
        if missing:
            raise ValueError(
                "incomplete authentication configuration: "
                + ", ".join(missing)
                + " must be set when ADRIANO_OIDC_AUTHORITY is set (client "
                "id and secret, session key) or ADRIANO_DEV_AUTH_ENABLED "
                "is true (session key)"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached :class:`Settings` instance.

    :returns: The lazily constructed, memoised settings object.
    """
    return Settings()  # pyright: ignore[reportCallIssue]
