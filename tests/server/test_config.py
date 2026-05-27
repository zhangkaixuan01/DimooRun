from pathlib import Path

import pytest
from dimoo_run.core.config import Settings
from dimoo_run.server import create_app
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_settings_defaults_to_dev_mode() -> None:
    settings = Settings()

    assert settings.runtime.mode == "dev"
    assert settings.runtime.environment == "local"
    assert settings.database.url == "sqlite:///./data/dimoorun.db"
    assert settings.redis.url == "redis://localhost:6379/0"
    assert settings.console.enabled is True
    assert settings.console.cors_origins == ["http://127.0.0.1:5173", "http://localhost:5173"]
    assert settings.object_store.bucket == "dimoorun-artifacts"
    assert settings.observability.tracing is False


def test_settings_loads_repository_dotenv_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DIMOORUN_ENVIRONMENT", raising=False)
    (tmp_path / ".env").write_text("DIMOORUN_ENVIRONMENT=dotenv-local\n", encoding="utf-8")

    settings = Settings.from_env()

    assert settings.runtime.environment == "dotenv-local"


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
    assert settings.console.cors_origins == [
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
    ]
    assert settings.object_store.bucket == "artifacts"
    assert settings.observability.tracing is True


def test_settings_always_allows_localhost_and_loopback_console_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIMOORUN_CORS_ORIGINS", "http://localhost:8080")

    settings = Settings.from_env()

    assert "http://127.0.0.1:5173" in settings.console.cors_origins
    assert "http://localhost:5173" in settings.console.cors_origins


def test_cors_preflight_allows_loopback_console_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIMOORUN_CORS_ORIGINS", "http://localhost:5173")
    client = TestClient(create_app())

    response = client.options(
        "/v1/runs",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-tenant-id,x-project-id,x-request-id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
