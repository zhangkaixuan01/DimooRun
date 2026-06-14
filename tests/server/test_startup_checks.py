from collections.abc import Callable

import pytest
from dimoo_run.core.config import Settings
from dimoo_run.core.startup_checks import (
    StartupConfigurationError,
    enforce_startup_settings,
)


def _safe_production_settings() -> Settings:
    return Settings.model_validate(
        {
            "runtime": {
                "mode": "production",
                "environment": "prod",
                "native_runtime_store": "sqlalchemy",
            },
            "database": {"url": "postgresql+psycopg://prod-user:prod-pass@db:5432/dimoorun"},
            "redis": {"url": "redis://redis:6379/0"},
            "console": {
                "enabled": True,
                "cors_origins": ["https://console.example.com"],
            },
            "object_store": {
                "backend": "s3",
                "endpoint_url": "https://s3.example.com",
                "bucket": "dimoorun-prod",
                "access_key": "prod-access-key",
                "secret_key": "prod-secret-key",
                "local_root": "./data/artifacts",
            },
        }
    )


@pytest.fixture(autouse=True)
def clear_prod_related_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DIMOORUN_DEV_API_KEY", raising=False)
    monkeypatch.delenv("DIMOORUN_SECRET_PROVIDER", raising=False)
    monkeypatch.delenv("DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD", raising=False)


def test_production_startup_accepts_safe_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "vault")
    monkeypatch.setenv("DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD", "ProdOnly-ChangeMe-123!")

    enforce_startup_settings(_safe_production_settings())


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (
            lambda settings: settings.model_copy(
                update={
                    "database": settings.database.model_copy(
                        update={"url": "sqlite:///./data/dimoorun.db"}
                    )
                }
            ),
            "Production mode cannot use SQLite.",
        ),
        (
            lambda settings: settings.model_copy(
                update={
                    "runtime": settings.runtime.model_copy(
                        update={"native_runtime_store": "memory"}
                    )
                }
            ),
            "Production mode cannot use the in-memory runtime store.",
        ),
        (
            lambda settings: settings.model_copy(
                update={
                    "object_store": settings.object_store.model_copy(update={"backend": "local"})
                }
            ),
            "Production mode requires object storage instead of memory/local artifacts.",
        ),
        (
            lambda settings: settings.model_copy(
                update={
                    "object_store": settings.object_store.model_copy(
                        update={"access_key": "dimoorun"}
                    )
                }
            ),
            "Production mode cannot use the default object store access key.",
        ),
        (
            lambda settings: settings.model_copy(
                update={
                    "object_store": settings.object_store.model_copy(
                        update={"secret_key": "dimoorun-dev-secret"}
                    )
                }
            ),
            "Production mode cannot use the default object store secret key.",
        ),
        (
            lambda settings: settings.model_copy(
                update={
                    "console": settings.console.model_copy(
                        update={
                            "cors_origins": [
                                "https://console.example.com",
                                "http://localhost:5173",
                            ]
                        }
                    )
                }
            ),
            "Production mode cannot keep local dev CORS origins enabled.",
        ),
    ],
)
def test_production_startup_rejects_unsafe_settings(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[Settings], Settings],
    expected_error: str,
) -> None:
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "vault")
    settings = mutate(_safe_production_settings())

    with pytest.raises(StartupConfigurationError) as exc_info:
        enforce_startup_settings(settings)

    assert expected_error in exc_info.value.errors


def test_production_startup_requires_secret_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "memory")

    with pytest.raises(StartupConfigurationError) as exc_info:
        enforce_startup_settings(_safe_production_settings())

    assert "Production mode requires a configured secret provider." in exc_info.value.errors


def test_production_startup_rejects_dev_api_key_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "vault")
    monkeypatch.setenv("DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD", "ProdOnly-ChangeMe-123!")
    monkeypatch.setenv("DIMOORUN_DEV_API_KEY", "dev-local-key")

    with pytest.raises(StartupConfigurationError) as exc_info:
        enforce_startup_settings(_safe_production_settings())

    assert "Production mode cannot expose DIMOORUN_DEV_API_KEY." in exc_info.value.errors


def test_production_startup_requires_explicit_bootstrap_admin_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "vault")

    with pytest.raises(StartupConfigurationError) as exc_info:
        enforce_startup_settings(_safe_production_settings())

    assert (
        "Production mode requires an explicit non-default "
        "DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD."
    ) in exc_info.value.errors


@pytest.mark.parametrize("password", ["admin123", "admin12345"])
def test_production_startup_rejects_default_bootstrap_admin_password(
    monkeypatch: pytest.MonkeyPatch,
    password: str,
) -> None:
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "vault")
    monkeypatch.setenv("DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD", password)

    with pytest.raises(StartupConfigurationError) as exc_info:
        enforce_startup_settings(_safe_production_settings())

    assert (
        "Production mode cannot use the default "
        "DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD."
    ) in exc_info.value.errors
