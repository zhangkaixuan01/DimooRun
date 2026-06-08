from pathlib import Path
from typing import Any

from dimoo_run.api.dependencies import (
    default_api_key_authenticator,
    reset_api_key_authenticator,
)


def test_reset_api_key_authenticator_does_not_initialize_new_sqlite_database(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "auth-reset.db"
    monkeypatch.setenv("DIMOORUN_RUNTIME_MODE", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    reset_api_key_authenticator()

    assert database_path.exists() is False

    default_api_key_authenticator()

    assert database_path.exists() is True
