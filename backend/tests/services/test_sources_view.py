"""Unit tests for :func:`app.services.sources_view.config_error_code`."""

from app.catalog_config import SourceRegistration
from app.services.sources_view import config_error_code
from app.sources.port import ConfigErrorCode
from app.storage.port import PollStatus, Registration


def _stored(config_error: str | None) -> Registration:
    """Build a stored registration with *config_error*."""
    return Registration(
        id="central",
        type="gitlab",
        config={},
        enabled=config_error is None,
        config_error=config_error,
        last_attempt_at=None,
        last_success_at=None,
        last_status=PollStatus.NEVER,
        last_error=None,
    )


def _configured(code: ConfigErrorCode | None) -> SourceRegistration:
    """Build a configured registration whose error has *code*."""
    return SourceRegistration(
        id="central",
        type="gitlab",
        position=0,
        config={},
        enabled=code is None,
        config_error=None if code is None else "readable text",
        config_error_code=code,
    )


def test_no_config_error_has_no_code() -> None:
    """Ensure a registration without a config error has no code."""
    assert config_error_code(_stored(None), _configured(None)) is None


def test_code_comes_from_the_loaded_configuration() -> None:
    """Ensure the code is the one set where the error was produced."""
    code = config_error_code(
        _stored("token_env: ... is not set"),
        _configured(ConfigErrorCode.TOKEN_ENV_MISSING),
    )

    assert code is ConfigErrorCode.TOKEN_ENV_MISSING


def test_registration_missing_from_configuration_is_removed() -> None:
    """Ensure a stored registration no longer configured is coded so."""
    code = config_error_code(_stored("no longer in catalog.yaml"), None)

    assert code is ConfigErrorCode.REMOVED_FROM_CONFIG


def test_uncoded_error_falls_back_to_other() -> None:
    """Ensure an error stored without a matching config code is other."""
    code = config_error_code(_stored("stale text"), _configured(None))

    assert code is ConfigErrorCode.OTHER
