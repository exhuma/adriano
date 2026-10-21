"""
Settings of the ``gitlab`` source type, validated without I/O.

Parses the type-specific options (``base_url``, ``token_env``), the
``scope`` and the ``published_ref`` of a registration into a
:class:`GitLabConfig`; see :mod:`app.sources.gitlab` for their meaning.
The token is resolved from the injected environment and held as a
:class:`pydantic.SecretStr`; messages name the env var only.

Public API: :data:`PROJECT_DEFAULT`, :class:`GitLabScope`,
:class:`GitLabConfig`, :func:`parse_settings`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.sources.port import ConfigErrorCode, SourceConfigError
from app.sources.registry import SourceSettings, parse_options

#: ``published_ref`` value selecting each project's default branch.
PROJECT_DEFAULT = "@project-default"

type _EnvName = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
]


class _Options(BaseModel):
    """Type-specific settings of the ``gitlab`` type."""

    model_config = ConfigDict(extra="forbid")

    base_url: str
    token_env: _EnvName

    @field_validator("base_url")
    @classmethod
    def _https_url(cls, value: str) -> str:
        """
        Require a plain ``https://`` instance URL.

        :param value: Configured URL.
        :returns: The URL without trailing slash.
        :raises ValueError: If it is not ``https`` or carries
            credentials, a query or a fragment.
        """
        parts = urlsplit(value.strip())
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError("must be an https:// URL")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError(
                "must not contain credentials, a query or a fragment"
            )
        return value.strip().rstrip("/")


def _clean_paths(values: list[str]) -> list[str]:
    """
    Normalise namespace paths (strip slashes, drop blanks).

    :param values: Configured paths.
    :returns: Cleaned paths.
    :raises ValueError: If a path is blank.
    """
    cleaned = [value.strip().strip("/") for value in values]
    if not all(cleaned):
        raise ValueError("paths must not be empty")
    return cleaned


class _Scope(BaseModel):
    """``scope`` of a ``gitlab`` registration."""

    model_config = ConfigDict(extra="forbid")

    groups: list[str] = Field(default_factory=list)
    include_subgroups: bool = False
    projects: list[str] = Field(default_factory=list)

    @field_validator("groups", "projects")
    @classmethod
    def _clean(cls, values: list[str]) -> list[str]:
        """
        Normalise the configured paths.

        :param values: Configured paths.
        :returns: Cleaned paths.
        """
        return _clean_paths(values)

    @model_validator(mode="after")
    def _not_everything(self) -> Self:
        """
        Require at least one group or project.

        :returns: The scope.
        :raises ValueError: If both lists are empty.
        """
        if not self.groups and not self.projects:
            raise ValueError("name at least one group or project")
        return self


@dataclass(frozen=True, slots=True)
class GitLabScope:
    """
    Which projects a registration owns.

    :param groups: Casefolded group paths.
    :param include_subgroups: Whether descendant namespaces count.
    :param projects: Casefolded explicit project paths.
    """

    groups: frozenset[str]
    include_subgroups: bool
    projects: frozenset[str]

    def contains(self, project: str) -> bool:
        """
        Tell whether a project path is in scope.

        :param project: Full project path (``group/sub/project``).
        :returns: ``True`` if listed explicitly or under a scoped group.
        """
        key = project.strip("/").casefold()
        if key in self.projects:
            return True
        parent = key.rpartition("/")[0]
        return any(
            parent == group
            or (self.include_subgroups and parent.startswith(group + "/"))
            for group in self.groups
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class GitLabConfig:
    """
    Validated settings of one ``gitlab`` registration.

    :param base_url: Instance URL without trailing slash.
    :param token: Access token.
    :param token_env: Env var name of the token (for messages).
    :param scope: Scope predicate.
    :param groups: Configured group paths, as written.
    :param projects: Configured project paths, as written.
    :param path: ADR path inside each project (may be empty).
    :param published_ref: Branch name or :data:`PROJECT_DEFAULT`.
    """

    base_url: str
    token: SecretStr
    token_env: str
    scope: GitLabScope
    groups: tuple[str, ...]
    projects: tuple[str, ...]
    path: str
    published_ref: str


def parse_settings(
    settings: SourceSettings, env: Mapping[str, str]
) -> GitLabConfig:
    """
    Validate a ``gitlab`` registration (no I/O).

    :param settings: Common settings plus ``options`` and ``scope``.
    :param env: Environment used to resolve ``token_env``.
    :returns: The configuration.
    :raises SourceConfigError: If the settings are invalid or the token
        env var is not set (the value is never echoed).
    """
    options = parse_options(_Options, settings.options)
    scope = parse_options(_Scope, settings.scope, prefix="scope")
    ref = settings.published_ref
    if ref.startswith("@") and ref != PROJECT_DEFAULT:
        raise SourceConfigError(
            f"published_ref: must be a branch name or {PROJECT_DEFAULT!r}",
            config_code=ConfigErrorCode.INVALID_PUBLISHED_REF,
        )
    token = SecretStr(env.get(options.token_env, ""))
    if not token.get_secret_value():
        raise SourceConfigError(
            f"token_env: GitLab token env var {options.token_env} is not set",
            config_code=ConfigErrorCode.TOKEN_ENV_MISSING,
        )
    return GitLabConfig(
        base_url=options.base_url,
        token=token,
        token_env=options.token_env,
        scope=GitLabScope(
            groups=frozenset(g.casefold() for g in scope.groups),
            include_subgroups=scope.include_subgroups,
            projects=frozenset(p.casefold() for p in scope.projects),
        ),
        groups=tuple(scope.groups),
        projects=tuple(scope.projects),
        path=settings.path,
        published_ref=ref,
    )
