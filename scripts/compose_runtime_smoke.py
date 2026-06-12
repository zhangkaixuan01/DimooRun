from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast

SERVER_HEALTH_URL = "http://127.0.0.1:8000/healthz"
CONSOLE_URL = "http://127.0.0.1:5173/"
BACKUP_DRY_RUN_URL = "http://127.0.0.1:8000/v1/backups/dry-run"
RESTORE_DRY_RUN_URL = "http://127.0.0.1:8000/v1/backups/restore-dry-run"
ADMIN_HEADERS = {
    "Authorization": "Bearer dev-local-key",
    "X-Tenant-Id": "1",
    "X-Project-Id": "1",
    "X-Environment": "local",
    "X-Request-Id": "req_compose_runtime_smoke",
    "Content-Type": "application/json",
}


@dataclass(frozen=True)
class ComposeRuntimeSmokeResult:
    errors: list[str] = field(default_factory=list)
    checked_steps: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class ComposeRuntimeRunner:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run(self, command: list[str], timeout_seconds: int) -> None:
        subprocess.run(
            command,
            cwd=self.root,
            check=True,
            timeout=timeout_seconds,
        )

    def probe_url(self, url: str, timeout_seconds: int) -> None:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            if response.status >= 400:
                raise RuntimeError(f"{url} returned HTTP {response.status}")

    def request_json(
        self,
        url: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            if response.status >= 400:
                raise RuntimeError(f"{url} returned HTTP {response.status}")
            return cast(dict[str, Any], json.loads(response.read().decode("utf-8")))


class RuntimeSmokeRunner(Protocol):
    def run(self, command: list[str], timeout_seconds: int) -> None: ...

    def probe_url(self, url: str, timeout_seconds: int) -> None: ...

    def request_json(
        self,
        url: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]: ...


def run_compose_runtime_smoke(
    root: Path,
    *,
    runner: RuntimeSmokeRunner | None = None,
    retries: int = 30,
    probe_delay_seconds: float = 2.0,
) -> ComposeRuntimeSmokeResult:
    active_runner = runner or ComposeRuntimeRunner(root)
    errors: list[str] = []
    checked_steps: list[str] = []

    try:
        active_runner.run(["docker", "compose", "config", "--quiet"], 60)
        checked_steps.append("compose-config")
        active_runner.run(["docker", "compose", "up", "--build", "--detach"], 900)
        checked_steps.append("compose-up")
        _wait_for_url(active_runner, SERVER_HEALTH_URL, retries, probe_delay_seconds)
        checked_steps.append("server-health")
        _wait_for_url(active_runner, CONSOLE_URL, retries, probe_delay_seconds)
        checked_steps.append("console-health")
        active_runner.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "pg_isready",
                "-U",
                "dimoorun",
                "-d",
                "dimoorun",
            ],
            60,
        )
        checked_steps.append("postgres-ready")
        active_runner.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "minio",
                "sh",
                "-c",
                (
                    "mc alias set local http://localhost:9000 "
                    "$MINIO_ROOT_USER $MINIO_ROOT_PASSWORD >/dev/null 2>&1 && mc ls local"
                ),
            ],
            60,
        )
        checked_steps.append("minio-ready")
        _backup_restore_smoke(active_runner)
        checked_steps.append("backup-restore-dry-run")
        active_runner.run(["docker", "compose", "ps"], 60)
        checked_steps.append("compose-ps")
    except Exception as exc:
        errors.append(str(exc))
    finally:
        try:
            active_runner.run(["docker", "compose", "down", "--remove-orphans"], 300)
        except Exception as exc:
            errors.append(f"teardown failed: {exc}")

    return ComposeRuntimeSmokeResult(errors=errors, checked_steps=checked_steps)


def _backup_restore_smoke(runner: RuntimeSmokeRunner) -> None:
    backup_payload = {
        "plan_id": 1,
        "scope": "project",
        "targets": ["runs", "datasets", "audit_logs"],
        "storage_ref": "minio://dimoorun-backups/local",
    }
    restore_payload = {
        "backup_ref": "backup://2026-06-12/project",
        "restore_scope": "project",
        "targets": ["runs"],
        "destructive": True,
        "confirmation": "RESTORE PROJECT 1",
    }
    backup_response = runner.request_json(
        BACKUP_DRY_RUN_URL,
        payload=backup_payload,
        headers=ADMIN_HEADERS,
        timeout_seconds=10,
    )
    if backup_response.get("status") != "ready":
        raise RuntimeError("backup dry-run did not return ready status")
    restore_response = runner.request_json(
        RESTORE_DRY_RUN_URL,
        payload=restore_payload,
        headers=ADMIN_HEADERS,
        timeout_seconds=10,
    )
    if restore_response.get("status") != "ready":
        raise RuntimeError("restore dry-run did not return ready status")


def _wait_for_url(
    runner: RuntimeSmokeRunner,
    url: str,
    retries: int,
    delay_seconds: float,
) -> None:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            runner.probe_url(url, 5)
            return
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(delay_seconds)
    raise RuntimeError(f"{url} did not become ready: {last_error}")


def main() -> None:
    result = run_compose_runtime_smoke(Path("."))
    if not result.ok:
        for error in result.errors:
            print(f"Compose runtime smoke failed: {error}")
        raise SystemExit(1)
    print("Compose runtime smoke passed: " + ", ".join(result.checked_steps))


if __name__ == "__main__":
    main()
