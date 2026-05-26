import pytest
from dimoo_run.core.config import Settings
from pydantic import ValidationError


def test_settings_defaults_to_dev_mode() -> None:
    settings = Settings()

    assert settings.runtime.mode == "dev"
    assert settings.runtime.environment == "local"
    assert settings.database.url == "sqlite:///./data/dimoorun.db"
    assert settings.redis.url == "redis://localhost:6379/0"
    assert settings.console.enabled is True
    assert settings.console.cors_origins == ["http://localhost:5173"]
    assert settings.object_store.bucket == "dimoorun-artifacts"
    assert settings.observability.tracing is False


def test_runtime_mode_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"runtime": {"mode": "staging"}})


def test_settings_loads_production_foundation_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIMOORUN_RUNTIME_MODE", "production")
    monkeypatch.setenv("DIMOORUN_ENVIRONMENT", "compose")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://example")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("DIMOORUN_CORS_ORIGINS", "http://localhost:5173,http://localhost:8080")
    monkeypatch.setenv("OBJECT_STORE_BUCKET", "artifacts")
    monkeypatch.setenv("DIMOORUN_TRACING_ENABLED", "true")

    settings = Settings.from_env()

    assert settings.runtime.mode == "production"
    assert settings.runtime.environment == "compose"
    assert settings.database.url == "postgresql+psycopg://example"
    assert settings.redis.url == "redis://redis:6379/0"
    assert settings.console.cors_origins == ["http://localhost:5173", "http://localhost:8080"]
    assert settings.object_store.bucket == "artifacts"
    assert settings.observability.tracing is True
