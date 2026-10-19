"""
Validation of the ``sources`` section of ``catalog.yaml``.

Part of the configuration loader (:mod:`app.catalog_config`, which
re-exports the public names). Common registration fields are validated
here; type-specific settings are handed to the source type registry
(:mod:`app.sources.registry`). Push tokens are resolved from env var
names and kept as :class:`pydantic.SecretStr`; the stored ``config`` is
secret-free (secret-looking keys are redacted defensively).

Public API: :data:`NonEmptyStr`, :class:`ConfigProblem`,
:class:`ConfigContext`, :class:`SourceRegistration`,
:func:`parse_sources`.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    ValidationError,
    field_validator,
)
from pydantic import JsonValue as PydanticJson

from app.domain.frontmatter import json_safe
from app.domain.issues import Severity
from app.sources.port import SourceConfigError
from app.sources.registry import (
    SourceBinding,
    SourceSettings,
    SourceTypeRegistry,
)
from app.storage.values import IntakeKind, JsonObject, RegistrationConfig
from app.validation_messages import describe_validation_error

_SECRET_HINTS = ("token", "password", "secret", "key")
_REDACTED = "***redacted***"

#: A string that is not blank (surrounding whitespace stripped).
type NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
type _EnvName = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
]


@dataclass(frozen=True, slots=True)
class ConfigProblem:
    """
    One configuration finding.

    :param severity: ``error`` (something is disabled) or ``warning``.
    :param location: Where in the file, e.g. ``sources[1] (central)``.
    :param message: Readable, secret-free description.
    """

    severity: Severity
    location: str
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceRegistration:
    """
    One configured source registration.

    :param id: Stable registration id.
    :param type: Source type name.
    :param position: Index in the configuration (ownership order).
    :param config: Non-secret settings as stored in the database.
    :param enabled: ``False`` when the entry is invalid.
    :param config_error: Why the entry is disabled.
    :param path: ADR path inside each project.
    :param published_ref: Configured published ref.
    :param intake: Enabled intake mechanisms.
    :param push_tokens: Resolved CI push tokens (never logged).
    :param binding: Adapter factory; ``None`` when disabled.
    :param warnings: Non-fatal findings for this registration.
    """

    id: str
    type: str
    position: int
    config: JsonObject
    enabled: bool
    config_error: str | None = None
    path: str = "doc/decisions"
    published_ref: str = ""
    intake: frozenset[IntakeKind] = frozenset()
    push_tokens: tuple[SecretStr, ...] = field(default=(), repr=False)
    binding: SourceBinding | None = field(default=None, repr=False)
    warnings: tuple[str, ...] = ()

    @property
    def pollable(self) -> bool:
        """
        Tell whether polling may run for this registration.

        :returns: ``True`` if enabled with ``poll`` intake.
        """
        return (
            self.enabled
            and self.binding is not None
            and IntakeKind.POLL in self.intake
        )

    def to_storage(self) -> RegistrationConfig:
        """
        Convert to the value synced into ``source_registration``.

        :returns: The registration config (no secrets).
        """
        return RegistrationConfig(
            id=self.id,
            type=self.type,
            config=self.config,
            enabled=self.enabled,
            config_error=self.config_error,
        )


class _SourceEntry(BaseModel):
    """Common fields of a ``sources`` entry; extras are type-specific."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: Annotated[
        str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    ]
    type: NonEmptyStr
    path: str = "doc/decisions"
    published_ref: NonEmptyStr
    scope: dict[str, PydanticJson] = Field(default_factory=dict)
    intake: list[Literal["poll", "push"]] = Field(
        default_factory=lambda: ["poll"], min_length=1
    )
    push_tokens_env: list[_EnvName] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def _relative_path(cls, value: str) -> str:
        """
        Normalise the ADR path to a project-relative POSIX path.

        A leading ``/`` means the project root, so it is stripped.

        :param value: Configured path.
        :returns: The path without leading/trailing slashes.
        :raises ValueError: If it leaves the project (``..``).
        """
        stripped = value.strip().strip("/")
        if ".." in PurePosixPath(stripped).parts:
            raise ValueError("must stay inside the project (no `..`)")
        return stripped


@dataclass(slots=True)
class ConfigContext:
    """
    Shared state while parsing one file.

    :param env: Environment used to resolve secret env var names.
    :param registry: Source type registry.
    :param base_dir: Directory for relative paths in source settings.
    :param problems: Findings collected so far.
    """

    env: Mapping[str, str]
    registry: SourceTypeRegistry
    base_dir: Path
    problems: list[ConfigProblem] = field(default_factory=list)

    def error(self, location: str, message: str) -> None:
        """
        Record an error.

        :param location: Where in the file.
        :param message: Description.
        """
        self.problems.append(ConfigProblem(Severity.ERROR, location, message))

    def warning(self, location: str, message: str) -> None:
        """
        Record a warning.

        :param location: Where in the file.
        :param message: Description.
        """
        self.problems.append(ConfigProblem(Severity.WARNING, location, message))


def _is_secret_key(key: str) -> bool:
    """
    Tell whether a setting name looks like it holds a secret value.

    :param key: Setting name.
    :returns: ``True`` unless it is an env var reference (``*_env``).
    """
    lowered = key.lower()
    if lowered.endswith("_env"):
        return False
    return any(hint in lowered for hint in _SECRET_HINTS)


def _public_config(item: Mapping[str, object]) -> JsonObject:
    """
    Build the storable, secret-free settings of a registration.

    :param item: Raw ``sources`` entry.
    :returns: All keys except ``id``/``type``; secret-looking keys
        redacted.
    """
    return {
        str(key): _REDACTED if _is_secret_key(str(key)) else json_safe(value)
        for key, value in item.items()
        if key not in ("id", "type")
    }


def _push_tokens(
    entry: _SourceEntry, env: Mapping[str, str]
) -> tuple[tuple[SecretStr, ...], tuple[str, ...]]:
    """
    Resolve the push tokens of a registration.

    :param entry: Validated entry.
    :param env: Environment mapping.
    :returns: The tokens and warnings (names only, never values).
    """
    tokens: list[SecretStr] = []
    warnings: list[str] = []
    for name in entry.push_tokens_env:
        value = env.get(name, "")
        if value:
            tokens.append(SecretStr(value))
        else:
            warnings.append(f"push token env var {name} is not set")
    if "push" in entry.intake and not tokens:
        warnings.append(
            "push intake is enabled but no push token is set; every push "
            "is refused"
        )
    return tuple(tokens), tuple(warnings)


def _disabled(
    item: Mapping[str, object], position: int, error: str
) -> SourceRegistration:
    """
    Build a disabled registration for an invalid entry.

    :param item: Raw entry (with a usable ``id``).
    :param position: Index in the file.
    :param error: Readable reason.
    :returns: The registration.
    """
    raw_type = item.get("type")
    return SourceRegistration(
        id=str(item["id"]),
        type=raw_type if isinstance(raw_type, str) else "",
        position=position,
        config=_public_config(item),
        enabled=False,
        config_error=error,
    )


def _source(
    item: Mapping[str, object], position: int, ctx: ConfigContext
) -> SourceRegistration:
    """
    Validate one entry that has a usable, unique id.

    :param item: Raw entry.
    :param position: Index in the file.
    :param ctx: Parse context.
    :returns: The registration, disabled when invalid.
    """
    try:
        entry = _SourceEntry.model_validate(item)
    except ValidationError as exc:
        return _disabled(item, position, describe_validation_error(exc))
    settings = SourceSettings(
        id=entry.id,
        type=entry.type,
        path=entry.path,
        published_ref=entry.published_ref,
        scope=entry.scope,
        options=dict(entry.model_extra or {}),
        base_dir=ctx.base_dir,
    )
    try:
        binding = ctx.registry.validate(settings, ctx.env)
    except SourceConfigError as exc:
        return _disabled(item, position, exc.message)
    tokens, warnings = _push_tokens(entry, ctx.env)
    return SourceRegistration(
        id=entry.id,
        type=entry.type,
        position=position,
        config=_public_config(item),
        enabled=True,
        path=entry.path,
        published_ref=entry.published_ref,
        intake=frozenset(IntakeKind(kind) for kind in entry.intake),
        push_tokens=tokens,
        binding=binding,
        warnings=warnings,
    )


def _entry_id(item: object) -> str | None:
    """
    Extract a usable id from a raw entry.

    :param item: Raw entry.
    :returns: The id, or ``None``.
    """
    if not isinstance(item, dict):
        return None
    raw_id = item.get("id")
    return raw_id if isinstance(raw_id, str) and raw_id.strip() else None


def parse_sources(
    raw: object, ctx: ConfigContext
) -> tuple[SourceRegistration, ...]:
    """
    Validate the ``sources`` section.

    Entries without a usable or with a duplicate ``id`` are reported and
    skipped; invalid entries become disabled registrations.

    :param raw: Raw section value.
    :param ctx: Parse context.
    :returns: Registrations in file order.
    """
    if raw is None:
        ctx.warning("sources", "no sources are configured")
        return ()
    if not isinstance(raw, list):
        ctx.error("sources", "must be a list of registrations")
        return ()
    result: list[SourceRegistration] = []
    for position, item in enumerate(raw):
        location = f"sources[{position}]"
        source_id = _entry_id(item)
        if source_id is None:
            ctx.error(location, "entry has no `id`; it is ignored")
            continue
        if any(source.id == source_id for source in result):
            ctx.error(location, f"duplicate id {source_id!r}; it is ignored")
            continue
        source = _source(item, position, ctx)
        location = f"{location} ({source_id})"
        if source.config_error is not None:
            ctx.error(location, f"disabled: {source.config_error}")
        for message in source.warnings:
            ctx.warning(location, message)
        result.append(source)
    return tuple(result)
