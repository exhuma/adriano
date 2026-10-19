"""
Load and validate ``catalog.yaml``: sources, approval policy and RBAC.

The file (``ADRIANO_CONFIG_FILE``) is read once at startup; changes need
a restart. Validation never aborts the whole load:

- An invalid ``sources`` entry becomes a *disabled* registration with a
  readable ``config_error``; the other registrations keep working. An
  entry without a usable ``id`` (or with a duplicate one) cannot be
  stored and is only reported. Type-specific settings are validated by
  the source type registry (:mod:`app.sources.registry`), i.e. at the
  adapter boundary. See :mod:`app.source_config`.
- A missing ``approval_policy`` yields :attr:`PolicyStatus.MISSING`, an
  invalid one :attr:`PolicyStatus.INVALID`, each with a message. Neither
  is ever treated as "approval not required".
- An invalid ``rbac`` section grants no permissions.
- A missing or unparseable file yields an empty configuration with
  :attr:`ConfigFileStatus.MISSING` / :attr:`ConfigFileStatus.INVALID`.

Every finding is a :class:`ConfigProblem` (``check-config`` exits
non-zero when one has error severity).

Secrets are referenced by environment variable **name** (for example
``push_tokens_env``, GitLab ``token_env``). Values are resolved from the
injected environment mapping, held as :class:`pydantic.SecretStr`, never
logged, never part of messages and never stored in the registration
``config``.

Public API: :class:`ConfigFileStatus`, :class:`Permission`,
:class:`PolicyConfig`, :class:`RbacConfig`, :class:`CatalogConfig`,
:func:`load_catalog_config`, :func:`parse_catalog_config`, and
re-exported from :mod:`app.source_config`: :class:`ConfigProblem`,
:class:`SourceRegistration`.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
)

from app.domain.approval import Policy, PolicyStatus
from app.domain.issues import Severity
from app.source_config import (
    ConfigContext,
    ConfigProblem,
    NonEmptyStr,
    SourceRegistration,
    parse_sources,
)
from app.sources.registry import SourceTypeRegistry
from app.storage.values import RegistrationConfig
from app.validation_messages import describe_validation_error

__all__ = [
    "CatalogConfig",
    "ConfigFileStatus",
    "ConfigProblem",
    "Permission",
    "PolicyConfig",
    "RbacConfig",
    "SourceRegistration",
    "load_catalog_config",
    "parse_catalog_config",
]

_KNOWN_SECTIONS = ("sources", "approval_policy", "rbac")

type _Principal = Annotated[str, StringConstraints(pattern=r"^[^|]+\|[^|]+$")]


class ConfigFileStatus(StrEnum):
    """Whether the configuration file could be read and parsed."""

    OK = "ok"
    MISSING = "missing"
    INVALID = "invalid"


class Permission(StrEnum):
    """Permissions an IdP role can grant (review comes from the policy)."""

    READ = "read"
    OPERATE = "operate"


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    """
    Status of the global approval policy.

    :param status: Configured, missing or invalid.
    :param policy: The policy when configured.
    :param message: Why it is missing or invalid.
    """

    status: PolicyStatus
    policy: Policy | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class RbacConfig:
    """
    IdP role -> permissions mapping.

    :param roles: Permissions granted per role name.
    """

    roles: Mapping[str, frozenset[Permission]] = field(default_factory=dict)

    def permissions_for(self, roles: Iterable[str]) -> frozenset[Permission]:
        """
        Collect the permissions granted by a caller's roles.

        :param roles: Role names from the verified token.
        :returns: The union of granted permissions.
        """
        granted: set[Permission] = set()
        for role in roles:
            granted |= self.roles.get(role, frozenset())
        return frozenset(granted)


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogConfig:
    """
    The loaded configuration.

    :param path: Configuration file path as given.
    :param file_status: Whether the file was read and parsed.
    :param sources: Registrations in configuration order.
    :param policy: Approval policy status.
    :param rbac: Role mapping.
    :param problems: All findings, in file order.
    """

    path: str
    file_status: ConfigFileStatus
    sources: tuple[SourceRegistration, ...] = ()
    policy: PolicyConfig = PolicyConfig(PolicyStatus.MISSING)
    rbac: RbacConfig = RbacConfig()
    problems: tuple[ConfigProblem, ...] = ()

    @property
    def has_errors(self) -> bool:
        """
        Tell whether any problem has error severity.

        :returns: ``True`` if at least one error was found.
        """
        return any(p.severity is Severity.ERROR for p in self.problems)

    def registration_configs(self) -> list[RegistrationConfig]:
        """
        Build the registration values to sync into storage.

        :returns: One value per registration.
        """
        return [source.to_storage() for source in self.sources]

    def get_source(self, source_id: str) -> SourceRegistration | None:
        """
        Find a registration by id.

        :param source_id: Registration id.
        :returns: The registration, or ``None``.
        """
        return next((s for s in self.sources if s.id == source_id), None)


class _Reviewers(BaseModel):
    """``approval_policy.reviewers``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    users: list[_Principal] = Field(default_factory=list)
    roles: list[NonEmptyStr] = Field(default_factory=list)


class _PolicyEntry(BaseModel):
    """``approval_policy``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonEmptyStr
    version: int = Field(ge=1)
    required: bool = True
    reviewers: _Reviewers = Field(default_factory=_Reviewers)
    allow_self_approval: bool = False


class _RbacEntry(BaseModel):
    """``rbac``."""

    model_config = ConfigDict(extra="forbid")

    roles: dict[NonEmptyStr, list[Permission]] = Field(default_factory=dict)


def _policy(data: Mapping[str, object], ctx: ConfigContext) -> PolicyConfig:
    """
    Validate the ``approval_policy`` section.

    :param data: Top-level mapping.
    :param ctx: Parse context.
    :returns: The policy status.
    """
    raw = data.get("approval_policy")
    if raw is None:
        message = (
            "no approval_policy is configured; every record needs "
            "approval and decisions are refused"
        )
        ctx.error("approval_policy", message)
        return PolicyConfig(PolicyStatus.MISSING, message=message)
    try:
        entry = _PolicyEntry.model_validate(raw)
    except ValidationError as exc:
        message = describe_validation_error(exc, "approval_policy")
        ctx.error(
            "approval_policy", f"invalid, decisions are refused: {message}"
        )
        return PolicyConfig(PolicyStatus.INVALID, message=message)
    if entry.required and not (entry.reviewers.users or entry.reviewers.roles):
        ctx.warning("approval_policy", "no reviewers: nobody can decide")
    return PolicyConfig(
        PolicyStatus.CONFIGURED,
        Policy(
            id=entry.id,
            version=entry.version,
            required=entry.required,
            reviewer_users=frozenset(entry.reviewers.users),
            reviewer_roles=frozenset(entry.reviewers.roles),
            allow_self_approval=entry.allow_self_approval,
        ),
    )


def _rbac(data: Mapping[str, object], ctx: ConfigContext) -> RbacConfig:
    """
    Validate the ``rbac`` section.

    :param data: Top-level mapping.
    :param ctx: Parse context.
    :returns: The role mapping (empty when missing or invalid).
    """
    raw = data.get("rbac")
    if raw is None:
        ctx.warning("rbac", "no rbac section; no role grants permissions")
        return RbacConfig()
    try:
        entry = _RbacEntry.model_validate(raw)
    except ValidationError as exc:
        ctx.error(
            "rbac",
            "invalid, no role grants permissions: "
            + describe_validation_error(exc, "rbac"),
        )
        return RbacConfig()
    return RbacConfig(
        {role: frozenset(perms) for role, perms in entry.roles.items()}
    )


def parse_catalog_config(
    data: Mapping[str, object],
    *,
    path: str,
    env: Mapping[str, str],
    registry: SourceTypeRegistry,
    base_dir: Path,
) -> CatalogConfig:
    """
    Validate an already parsed configuration mapping.

    :param data: Top-level YAML mapping.
    :param path: Configuration file path (for reporting).
    :param env: Environment used to resolve secret env var names.
    :param registry: Source type registry.
    :param base_dir: Directory for relative paths in source settings.
    :returns: The configuration with all problems found.
    """
    ctx = ConfigContext(env=env, registry=registry, base_dir=base_dir)
    for key in data:
        if key not in _KNOWN_SECTIONS:
            ctx.warning(str(key), "unknown section is ignored")
    sources = parse_sources(data.get("sources"), ctx)
    policy = _policy(data, ctx)
    rbac = _rbac(data, ctx)
    return CatalogConfig(
        path=path,
        file_status=ConfigFileStatus.OK,
        sources=sources,
        policy=policy,
        rbac=rbac,
        problems=tuple(ctx.problems),
    )


def _unloaded(
    path: str, status: ConfigFileStatus, message: str
) -> CatalogConfig:
    """
    Build the configuration of an unreadable file.

    :param path: Configuration file path.
    :param status: Missing or invalid.
    :param message: Readable reason.
    :returns: An empty configuration; the policy is missing/invalid.
    """
    policy_status = (
        PolicyStatus.MISSING
        if status is ConfigFileStatus.MISSING
        else PolicyStatus.INVALID
    )
    return CatalogConfig(
        path=path,
        file_status=status,
        policy=PolicyConfig(policy_status, message=message),
        problems=(ConfigProblem(Severity.ERROR, path, message),),
    )


def _read_yaml(path: Path) -> object:
    """
    Read and parse the YAML file.

    :param path: File path.
    :returns: The parsed document (``{}`` for an empty file).
    :raises OSError: If the file cannot be read.
    :raises UnicodeDecodeError: If it is not UTF-8.
    :raises yaml.YAMLError: If it is not valid YAML.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {} if data is None else data


def load_catalog_config(
    path: str | Path,
    *,
    env: Mapping[str, str],
    registry: SourceTypeRegistry,
) -> CatalogConfig:
    """
    Load and validate ``catalog.yaml``. Never raises for bad content.

    :param path: Configuration file path.
    :param env: Environment used to resolve secret env var names.
    :param registry: Source type registry.
    :returns: The configuration with all problems found.
    """
    file_path = Path(path)
    shown = str(path)
    try:
        data = _read_yaml(file_path)
    except FileNotFoundError:
        return _unloaded(
            shown,
            ConfigFileStatus.MISSING,
            f"configuration file {shown} not found; copy "
            f"catalog.example.yaml or set ADRIANO_CONFIG_FILE",
        )
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return _unloaded(
            shown,
            ConfigFileStatus.INVALID,
            f"cannot read {shown}: {exc}",
        )
    if not isinstance(data, dict):
        return _unloaded(
            shown, ConfigFileStatus.INVALID, "top level must be a mapping"
        )
    return parse_catalog_config(
        data,
        path=shown,
        env=env,
        registry=registry,
        base_dir=file_path.resolve().parent,
    )
