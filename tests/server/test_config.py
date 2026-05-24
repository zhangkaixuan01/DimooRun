import pytest
from dimoo_run.core.config import Settings
from pydantic import ValidationError


def test_settings_defaults_to_dev_mode() -> None:
    settings = Settings()

    assert settings.runtime.mode == "dev"
    assert settings.runtime.environment == "local"
    assert settings.database.url == "sqlite+aiosqlite:///./data/dimoorun.db"
    assert settings.redis.url == "redis://localhost:6379/0"
    assert settings.console.enabled is True
    assert settings.observability.tracing is False


def test_runtime_mode_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"runtime": {"mode": "staging"}})
