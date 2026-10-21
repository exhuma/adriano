"""
Source type registry: type name -> settings validator / adapter factory.

The catalog configuration loader (:mod:`app.catalog_config`) validates
the common registration fields and hands everything type-specific to
:meth:`SourceTypeRegistry.validate`. The validator registered for the
type checks the type-specific settings at the adapter boundary and
returns a :class:`SourceBinding`: a factory that opens the adapter for a
poll, plus the scope check used by push intake. Invalid settings raise
:class:`~app.sources.port.SourceConfigError`; the registration is then
disabled with that message, the rest of the catalog keeps working.

Adapter modules plug in at :func:`default_registry` (the only place that
names concrete adapters). A type listed in :data:`SUPPORTED_TYPES` but
not registered yet yields a readable "not available" error instead of a
crash; an unknown type yields an "unknown source type" error.

Validator contract (implemented by ``app.sources.filesystem`` and
``app.sources.gitlab``)::

    def validate_settings(
        settings: SourceSettings, env: Mapping[str, str]
    ) -> SourceBinding: ...

- read type-specific keys from ``settings.options`` (and the scope from
  ``settings.scope``), typically with :func:`parse_options`;
- resolve secrets from *env* by the configured env var **name**; never
  put a secret value in an error message or in a log line;
- resolve relative paths against ``settings.base_dir`` (the directory of
  ``catalog.yaml``);
- do not perform I/O; open clients only inside ``open_adapter``.

Public API: :data:`SUPPORTED_TYPES`, :class:`SourceSettings`,
:data:`AdapterOpener`, :class:`SourceBinding`,
:class:`SourceTypeValidator`, :class:`SourceTypeRegistry`,
:func:`parse_options`, :func:`default_registry`.
"""

from collections.abc import Callable, Collection, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ValidationError

from app.domain.frontmatter import JsonValue
from app.sources.port import (
    ConfigErrorCode,
    SourceAdapter,
    SourceConfigError,
)
from app.validation_messages import describe_validation_error

#: Source types of Product Phase 1 (see ``phases/DECISIONS.md``).
SUPPORTED_TYPES = ("filesystem", "gitlab")


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceSettings:
    """
    Validated common settings of one registration plus raw extras.

    :param id: Registration id.
    :param type: Source type name.
    :param path: ADR path inside each project.
    :param published_ref: Configured published ref (adapter-specific
        meaning, e.g. ``"@project-default"`` for GitLab).
    :param scope: Raw ``scope`` mapping; its shape is type-specific.
    :param options: All other, type-specific keys (e.g. ``root``,
        ``base_url``, ``token_env``).
    :param base_dir: Directory of the configuration file, for resolving
        relative paths.
    """

    id: str
    type: str
    path: str
    published_ref: str
    scope: Mapping[str, JsonValue]
    options: Mapping[str, JsonValue]
    base_dir: Path


#: Opens an adapter for the duration of one poll (``async with``).
type AdapterOpener = Callable[[], AbstractAsyncContextManager[SourceAdapter]]


def _whole_scope(_project: str) -> bool:
    """
    Accept every project (default scope check).

    :param _project: Project path.
    :returns: Always ``True``.
    """
    return True


@dataclass(frozen=True, slots=True)
class SourceBinding:
    """
    A validated registration, ready to open its adapter.

    :param open_adapter: Opens the adapter for one poll.
    :param in_scope: Tells whether a project path is within the
        registration scope (used by push intake, which never calls the
        adapter).
    """

    open_adapter: AdapterOpener
    in_scope: Callable[[str], bool] = _whole_scope


class SourceTypeValidator(Protocol):
    """Validates type-specific settings and binds the adapter factory."""

    def __call__(
        self, settings: SourceSettings, env: Mapping[str, str]
    ) -> SourceBinding:
        """
        Validate one registration of this type.

        :param settings: Common settings plus type-specific options.
        :param env: Environment used to resolve secret env var names.
        :returns: The binding.
        :raises SourceConfigError: If the settings are invalid.
        """
        ...


class SourceTypeRegistry:
    """
    Maps source type names to their validators.

    :param validators: Initially registered validators by type name.
    :param pending: Known type names whose adapter is not available.
    """

    def __init__(
        self,
        validators: Mapping[str, SourceTypeValidator] | None = None,
        *,
        pending: Collection[str] = (),
    ) -> None:
        """
        Store the initial validators.

        :param validators: Initially registered validators.
        :param pending: Known but unavailable type names.
        """
        self._validators: dict[str, SourceTypeValidator] = dict(
            validators or {}
        )
        self._pending = set(pending) - set(self._validators)

    def register(self, name: str, validator: SourceTypeValidator) -> None:
        """
        Register (or replace) the validator of a source type.

        :param name: Type name as written in ``catalog.yaml``.
        :param validator: The validator.
        """
        self._validators[name] = validator
        self._pending.discard(name)

    @property
    def available(self) -> tuple[str, ...]:
        """
        Type names with a registered adapter.

        :returns: Sorted names.
        """
        return tuple(sorted(self._validators))

    def validate(
        self, settings: SourceSettings, env: Mapping[str, str]
    ) -> SourceBinding:
        """
        Validate one registration with the validator of its type.

        :param settings: Common settings plus type-specific options.
        :param env: Environment used to resolve secret env var names.
        :returns: The binding.
        :raises SourceConfigError: If the type is unknown or unavailable,
            or its settings are invalid.
        """
        validator = self._validators.get(settings.type)
        if validator is not None:
            return validator(settings, env)
        if settings.type in self._pending:
            raise SourceConfigError(
                f"source type {settings.type!r} is not available yet in "
                f"this build (its adapter is not implemented)",
                config_code=ConfigErrorCode.TYPE_UNAVAILABLE,
            )
        known = ", ".join(sorted(self._pending | set(self._validators)))
        raise SourceConfigError(
            f"unknown source type {settings.type!r}; supported: {known}",
            config_code=ConfigErrorCode.UNKNOWN_TYPE,
        )


def parse_options[M: BaseModel](
    model: type[M], data: Mapping[str, JsonValue], *, prefix: str = ""
) -> M:
    """
    Validate type-specific settings with a pydantic model.

    :param model: Model describing the settings (use ``extra="forbid"``).
    :param data: Raw settings.
    :param prefix: Location prefix for messages (e.g. ``"scope"``).
    :returns: The validated model.
    :raises SourceConfigError: With a readable, secret-free message.
    """
    try:
        return model.model_validate(dict(data))
    except ValidationError as exc:
        raise SourceConfigError(
            describe_validation_error(exc, prefix),
            config_code=ConfigErrorCode.INVALID_SETTINGS,
        ) from exc


def default_registry() -> SourceTypeRegistry:
    """
    Build the registry of the Phase 1 source types.

    Adapter hook: each adapter module registers its validator here.
    The adapter imports are local to this function because those
    modules import back from this one (``SourceBinding``,
    ``SourceSettings``, ``parse_options``); importing them at module
    level would be a circular import.

    :returns: The registry.
    """
    from app.sources import filesystem, gitlab

    registry = SourceTypeRegistry(pending=SUPPORTED_TYPES)
    registry.register("filesystem", filesystem.validate_settings)
    registry.register("gitlab", gitlab.validate_settings)
    return registry
