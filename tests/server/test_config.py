from pathlib import Path

import pytest
from dimoo_run.core.config import Settings
from dimoo_run.core.startup_checks import StartupConfigurationError
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
    assert settings.packages.cache_root == "./data/package-cache"
    assert settings.packages.oci_roots == ["./data/packages/oci"]


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
    monkeypatch.setenv(
        "DIMOORUN_OCI_PACKAGE_ROOTS",
        "/var/lib/dimoorun/packages,/srv/dimoorun/packages",
    )
    monkeypatch.setenv("DIMOORUN_PACKAGE_CACHE_ROOT", "/var/cache/dimoorun-packages")

    settings = Settings.from_env()

    assert settings.runtime.mode == "production"
    assert settings.runtime.environment == "compose"
    assert settings.database.url == "postgresql+psycopg://example"
    assert settings.redis.url == "redis://redis:6379/0"
    assert settings.console.cors_origins == ["http://localhost:5173", "http://localhost:8080"]
    assert settings.object_store.bucket == "artifacts"
    assert settings.observability.tracing is True
    assert settings.packages.cache_root == "/var/cache/dimoorun-packages"
    assert settings.packages.oci_roots == [
        "/var/lib/dimoorun/packages",
        "/srv/dimoorun/packages",
    ]


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


def test_create_app_rejects_unsafe_production_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIMOORUN_RUNTIME_MODE", "production")
    monkeypatch.delenv("DIMOORUN_SECRET_PROVIDER", raising=False)
    monkeypatch.delenv("DIMOORUN_DEV_API_KEY", raising=False)
    monkeypatch.delenv("DIMOORUN_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OBJECT_STORE_BACKEND", raising=False)
    monkeypatch.delenv("OBJECT_STORE_ACCESS_KEY", raising=False)
    monkeypatch.delenv("OBJECT_STORE_SECRET_KEY", raising=False)
    monkeypatch.delenv("DIMOORUN_NATIVE_RUNTIME_STORE", raising=False)

    with pytest.raises(StartupConfigurationError) as exc_info:
        create_app()

    message = str(exc_info.value)
    assert "Production mode cannot use SQLite." in message
    assert "Production mode cannot use the in-memory runtime store." in message
    assert "Production mode requires a configured secret provider." in message
