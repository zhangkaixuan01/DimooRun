import os

from dimoo_run.core.config import Settings

_DEV_CONSOLE_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}
_DEFAULT_OBJECT_STORE_ACCESS_KEY = "dimoorun"
_DEFAULT_OBJECT_STORE_SECRET_KEY = "dimoorun-dev-secret"
_DEFAULT_BOOTSTRAP_ADMIN_PASSWORDS = {"admin123", "admin12345"}


class StartupConfigurationError(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def validate_production_settings(settings: Settings) -> list[str]:
    errors: list[str] = []
    if settings.runtime.mode != "production":
        return errors
    if settings.database.url.startswith("sqlite"):
        errors.append("Production mode cannot use SQLite.")
    if settings.runtime.native_runtime_store == "memory":
        errors.append("Production mode cannot use the in-memory runtime store.")
    if settings.object_store.backend in {"memory", "local"}:
        errors.append("Production mode requires object storage instead of memory/local artifacts.")
    if settings.object_store.access_key == _DEFAULT_OBJECT_STORE_ACCESS_KEY:
        errors.append("Production mode cannot use the default object store access key.")
    if settings.object_store.secret_key == _DEFAULT_OBJECT_STORE_SECRET_KEY:
        errors.append("Production mode cannot use the default object store secret key.")
    if any(origin in _DEV_CONSOLE_ORIGINS for origin in settings.console.cors_origins):
        errors.append("Production mode cannot keep local dev CORS origins enabled.")
    if os.getenv("DIMOORUN_SECRET_PROVIDER", "memory") == "memory":
        errors.append("Production mode requires a configured secret provider.")
    if os.getenv("DIMOORUN_DEV_API_KEY"):
        errors.append("Production mode cannot expose DIMOORUN_DEV_API_KEY.")
    bootstrap_password = os.getenv("DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD")
    if bootstrap_password is None or not bootstrap_password.strip():
        errors.append(
            "Production mode requires an explicit non-default "
            "DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD."
        )
    elif bootstrap_password in _DEFAULT_BOOTSTRAP_ADMIN_PASSWORDS:
        errors.append(
            "Production mode cannot use the default "
            "DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD."
        )
    return errors


def enforce_startup_settings(settings: Settings) -> None:
    errors = validate_production_settings(settings)
    if errors:
        raise StartupConfigurationError(errors)
