"""Tests for the catalog configuration loader."""

import logging
from pathlib import Path

import pytest

from app.catalog_config import (
    ConfigFileStatus,
    Permission,
    load_catalog_config,
)
from app.composition import log_problems
from app.domain.approval import PolicyStatus
from app.domain.issues import Severity
from app.sources.port import ConfigErrorCode
from app.sources.registry import SourceTypeRegistry, default_registry
from app.storage.values import IntakeKind
from tests.fakes import FakeSource, FakeSourceType

SECRET = "s3cr3t-token-value"

POLICY = """
approval_policy:
  id: global
  version: 1
  required: true
  reviewers:
    users: ["https://idp.example.com|subject-123"]
    roles: [adr-reviewer]
  allow_self_approval: false
rbac:
  roles:
    admin: [read, operate]
    adr-reader: [read]
"""


def registry() -> SourceTypeRegistry:
    """
    Build a registry with the fake type plus the pending Phase 1 types.

    :returns: The registry.
    """
    result = default_registry()
    result.register("fake", FakeSourceType({"w": FakeSource()}))
    return result


def load(tmp_path: Path, text: str, env: dict[str, str] | None = None):
    """
    Write and load a configuration file.

    :param tmp_path: Temporary directory.
    :param text: YAML text.
    :param env: Environment mapping.
    :returns: The configuration.
    """
    path = tmp_path / "catalog.yaml"
    path.write_text(text, encoding="utf-8")
    return load_catalog_config(path, env=env or {}, registry=registry())


def test_valid_configuration_loads_everything(tmp_path: Path) -> None:
    """Ensure a valid file yields enabled registrations, policy and RBAC."""
    config = load(
        tmp_path,
        """
sources:
  - id: one
    type: fake
    world: w
    published_ref: main
    path: /doc/decisions/
    intake: [poll, push]
    push_tokens_env: [PUSH_ONE]
"""
        + POLICY,
        env={"PUSH_ONE": SECRET},
    )

    assert config.file_status is ConfigFileStatus.OK
    assert not config.has_errors
    (source,) = config.sources
    assert source.enabled and source.pollable
    assert source.path == "doc/decisions"
    assert source.intake == {IntakeKind.POLL, IntakeKind.PUSH}
    assert [t.get_secret_value() for t in source.push_tokens] == [SECRET]
    assert config.policy.status is PolicyStatus.CONFIGURED
    assert config.policy.policy is not None
    assert config.policy.policy.reviewer_roles == {"adr-reviewer"}
    assert config.rbac.permissions_for(["adr-reader", "x"]) == {Permission.READ}


def test_invalid_entry_is_disabled_and_others_keep_working(
    tmp_path: Path,
) -> None:
    """Ensure one bad registration is disabled with a readable error."""
    config = load(
        tmp_path,
        """
sources:
  - id: bad
    type: fake
    world: w
  - id: good
    type: fake
    world: w
    published_ref: main
"""
        + POLICY,
    )

    bad, good = config.sources
    assert not bad.enabled and not bad.pollable
    assert bad.config_error is not None
    assert "published_ref" in bad.config_error
    assert bad.config_error_code is ConfigErrorCode.INVALID_SETTINGS
    assert good.enabled
    assert good.config_error_code is None
    assert config.has_errors
    stored = {item.id: item for item in config.registration_configs()}
    assert stored["bad"].enabled is False
    assert stored["bad"].config_error == bad.config_error


def test_type_specific_settings_are_validated_by_the_registry(
    tmp_path: Path,
) -> None:
    """Ensure unknown and invalid typed settings disable."""
    config = load(
        tmp_path,
        """
sources:
  - {id: a, type: svn, published_ref: main}
  - {id: b, type: gitlab, published_ref: main}
  - {id: c, type: fake, published_ref: main, world: nowhere}
  - {id: d, type: fake, published_ref: main, world: w, extra: 1}
"""
        + POLICY,
    )

    errors = {s.id: s.config_error or "" for s in config.sources}
    assert "unknown source type 'svn'" in errors["a"]
    assert "base_url" in errors["b"]
    assert "unknown world" in errors["c"]
    assert "extra" in errors["d"]
    assert not any(s.enabled for s in config.sources)
    codes = {s.id: s.config_error_code for s in config.sources}
    assert codes == {
        "a": ConfigErrorCode.UNKNOWN_TYPE,
        "b": ConfigErrorCode.INVALID_SETTINGS,
        "c": ConfigErrorCode.OTHER,
        "d": ConfigErrorCode.INVALID_SETTINGS,
    }


def test_pending_source_type_is_reported_as_not_available(
    tmp_path: Path,
) -> None:
    """Ensure a known type without an adapter disables readably."""
    path = tmp_path / "catalog.yaml"
    path.write_text(
        "sources:\n  - {id: a, type: gitlab, published_ref: main}\n" + POLICY,
        encoding="utf-8",
    )

    config = load_catalog_config(
        path, env={}, registry=SourceTypeRegistry(pending=["gitlab"])
    )

    assert "not available yet" in (config.sources[0].config_error or "")
    assert (
        config.sources[0].config_error_code is ConfigErrorCode.TYPE_UNAVAILABLE
    )


def test_entries_without_usable_id_are_reported_not_stored(
    tmp_path: Path,
) -> None:
    """Ensure missing and duplicate ids are reported and skipped."""
    config = load(
        tmp_path,
        """
sources:
  - {type: fake, world: w, published_ref: main}
  - {id: x, type: fake, world: w, published_ref: main}
  - {id: x, type: fake, world: w, published_ref: dev}
  - just-a-string
"""
        + POLICY,
    )

    assert [s.id for s in config.sources] == ["x"]
    locations = [p.location for p in config.problems]
    assert locations == ["sources[0]", "sources[2]", "sources[3]"]


def test_missing_policy_is_missing_not_not_required(tmp_path: Path) -> None:
    """Ensure an absent approval_policy yields the missing status."""
    config = load(tmp_path, "sources: []\nrbac: {roles: {}}\n")

    assert config.policy.status is PolicyStatus.MISSING
    assert config.policy.policy is None
    assert config.policy.message
    assert config.has_errors


@pytest.mark.parametrize(
    "policy",
    [
        "{id: global, version: one}",
        "{id: global, version: 1, required: 'no'}",
        "{id: global, version: 1, reviewers: {users: [nobar]}}",
        "{id: global, version: 1, surprise: true}",
        "[not, a, mapping]",
    ],
)
def test_invalid_policy_is_invalid(tmp_path: Path, policy: str) -> None:
    """Ensure malformed policies are invalid with a message."""
    config = load(tmp_path, f"approval_policy: {policy}\n")

    assert config.policy.status is PolicyStatus.INVALID
    assert config.policy.policy is None
    assert config.policy.message


def test_invalid_rbac_grants_nothing(tmp_path: Path) -> None:
    """Ensure an unknown permission invalidates the RBAC section."""
    config = load(tmp_path, POLICY.replace("[read]", "[read, delete]"))

    assert config.rbac.roles == {}
    assert any(p.location == "rbac" for p in config.problems)


@pytest.mark.parametrize(
    ("text", "status"),
    [
        (None, ConfigFileStatus.MISSING),
        ("a: [b", ConfigFileStatus.INVALID),
        ("- a\n- b\n", ConfigFileStatus.INVALID),
    ],
)
def test_unloadable_files_yield_an_empty_configuration(
    tmp_path: Path, text: str | None, status: ConfigFileStatus
) -> None:
    """Ensure missing, broken or non-mapping files never raise."""
    path = tmp_path / "catalog.yaml"
    if text is not None:
        path.write_text(text, encoding="utf-8")

    config = load_catalog_config(path, env={}, registry=registry())

    assert config.file_status is status
    assert config.sources == ()
    assert config.policy.status is not PolicyStatus.CONFIGURED
    assert config.has_errors


def test_secrets_never_reach_storage_messages_or_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure resolved secrets and inline secret keys are redacted."""
    config = load(
        tmp_path,
        """
sources:
  - id: one
    type: fake
    world: w
    published_ref: main
    intake: [push]
    push_tokens_env: [PUSH_ONE, PUSH_UNSET]
  - id: two
    type: fake
    world: w
    published_ref: main
    token: inline-secret
"""
        + POLICY,
        env={"PUSH_ONE": SECRET},
    )
    with caplog.at_level(logging.DEBUG):
        log_problems(config)

    stored = {item.id: item for item in config.registration_configs()}
    assert stored["one"].config["push_tokens_env"] == [
        "PUSH_ONE",
        "PUSH_UNSET",
    ]
    assert stored["two"].config["token"] == "***redacted***"
    dumped = repr(config) + repr(config.registration_configs())
    assert SECRET not in dumped
    assert "inline-secret" not in dumped
    assert SECRET not in caplog.text
    assert "inline-secret" not in caplog.text
    warnings = [p for p in config.problems if p.severity is Severity.WARNING]
    assert any("PUSH_UNSET is not set" in p.message for p in warnings)


def test_example_configuration_is_valid_apart_from_unset_secrets() -> None:
    """Ensure catalog.example.yaml only fails on the unset GitLab token."""
    example = Path(__file__).resolve().parents[2] / "catalog.example.yaml"

    config = load_catalog_config(example, env={}, registry=default_registry())

    assert config.file_status is ConfigFileStatus.OK
    assert config.policy.status is PolicyStatus.CONFIGURED
    assert [s.id for s in config.sources] == ["central", "gitlab-platform"]
    central, gitlab = config.sources
    assert central.enabled and central.config_error is None
    assert gitlab.config_error is not None
    assert "ADRIANO_GITLAB_TOKEN_PLATFORM is not set" in gitlab.config_error
    assert gitlab.config_error_code is ConfigErrorCode.TOKEN_ENV_MISSING


def test_example_configuration_gitlab_entry_is_valid_with_a_token() -> None:
    """Ensure the example gitlab entry validates once its token is set."""
    example = Path(__file__).resolve().parents[2] / "catalog.example.yaml"
    env = {"ADRIANO_GITLAB_TOKEN_PLATFORM": SECRET}

    config = load_catalog_config(example, env=env, registry=default_registry())

    gitlab = config.sources[1]
    assert gitlab.enabled and gitlab.config_error is None
    assert gitlab.binding is not None
    assert gitlab.binding.in_scope("platform/sub/api")
    assert SECRET not in repr(config.registration_configs())
