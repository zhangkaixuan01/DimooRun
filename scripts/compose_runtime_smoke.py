from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast

SERVER_HEALTH_URL = "http://127.0.0.1:8000/healthz"
CONSOLE_URL = "http://127.0.0.1:5173/"
API_BASE_URL = "http://127.0.0.1:8000"
BACKUP_DRY_RUN_URL = "http://127.0.0.1:8000/v1/backups/dry-run"
RESTORE_DRY_RUN_URL = "http://127.0.0.1:8000/v1/backups/restore-dry-run"
TERMINAL_RUN_STATUSES = {"succeeded", "failed", "timeout", "canceled", "cancelled"}
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
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                if response.status >= 400:
                    raise RuntimeError(f"{url} returned HTTP {response.status}")
                return cast(dict[str, Any], json.loads(response.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{url} returned HTTP {exc.code}: {error_body}") from exc

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> object:
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                if response.status >= 400:
                    raise RuntimeError(f"{url} returned HTTP {response.status}")
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{url} returned HTTP {exc.code}: {error_body}") from exc


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

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> object: ...


def run_compose_runtime_smoke(
    root: Path,
    *,
    runner: RuntimeSmokeRunner | None = None,
    evidence_dir: Path | None = None,
    retries: int = 30,
    probe_delay_seconds: float = 2.0,
) -> ComposeRuntimeSmokeResult:
    active_runner = runner or ComposeRuntimeRunner(root)
    active_evidence_dir = evidence_dir or root / "compose-diagnostics"
    errors: list[str] = []
    checked_steps: list[str] = []
    created_env_file = False

    try:
        created_env_file = _ensure_compose_env(root)
        if created_env_file:
            checked_steps.append("env-file")
        active_runner.run(["docker", "compose", "config", "--quiet"], 60)
        checked_steps.append("compose-config")
        active_runner.run(["docker", "compose", "up", "--build", "--detach", "--wait"], 900)
        checked_steps.append("compose-up")
        _wait_for_url(active_runner, SERVER_HEALTH_URL, retries, probe_delay_seconds)
        checked_steps.append("server-health")
        _wait_for_url(active_runner, CONSOLE_URL, retries, probe_delay_seconds)
        checked_steps.append("console-health")
        checked_steps.append("activation:console health checked")
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
        activation_evidence = _activation_smoke(
            active_runner,
            root=root,
            retries=retries,
            delay_seconds=probe_delay_seconds,
        )
        checked_steps.extend(activation_evidence["checked_steps"])
        _write_activation_evidence_index(
            active_evidence_dir,
            root=root,
            evidence=activation_evidence,
        )
        checked_steps.append("activation:evidence index written")
        _backup_restore_smoke(active_runner)
        checked_steps.append("backup-restore-dry-run")
        active_runner.run(["docker", "compose", "ps"], 60)
        checked_steps.append("compose-ps")
    except Exception as exc:
        errors.append(str(exc))
    finally:
        try:
            active_runner.run(["docker", "compose", "down", "--remove-orphans", "--volumes"], 300)
        except Exception as exc:
            errors.append(f"teardown failed: {exc}")
        if created_env_file:
            env_path = root / ".env"
            if env_path.exists():
                env_path.unlink()

    return ComposeRuntimeSmokeResult(errors=errors, checked_steps=checked_steps)


def _activation_smoke(
    runner: RuntimeSmokeRunner,
    *,
    root: Path,
    retries: int,
    delay_seconds: float,
) -> dict[str, Any]:
    package_uri = "file:///workspace/examples/langgraph/support-agent"
    manifest = _support_agent_manifest()
    validation = runner.request_json(
        f"{API_BASE_URL}/v1/packages/validate",
        payload={
            "package_uri": package_uri,
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:build_graph",
            "manifest": manifest,
            "required_secret_refs": [],
        },
        headers=ADMIN_HEADERS,
        timeout_seconds=30,
    )
    validation_token = validation.get("validation_token")
    checked_steps = ["activation:package validation completed"]

    agent = runner.request_json(
        f"{API_BASE_URL}/v1/agents",
        payload={
            "name": "compose-smoke-support-agent",
            "description": "Compose runtime smoke activation agent",
        },
        headers=ADMIN_HEADERS,
        timeout_seconds=30,
    )
    agent_id = _required_id(agent, "agent")

    version = runner.request_json(
        f"{API_BASE_URL}/v1/agents/{agent_id}/versions",
        payload={
            "version": "0.1.0-compose-smoke",
            "package_uri": package_uri,
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:build_graph",
            "manifest": manifest | {"validation_token": validation_token},
            "capabilities": manifest["capabilities"],
            "status": "ready",
        },
        headers=ADMIN_HEADERS,
        timeout_seconds=30,
    )
    version_id = _required_id(version, "agent version")
    checked_steps.append("activation:agent version created")

    deployment = runner.request_json(
        f"{API_BASE_URL}/v1/deployments",
        payload={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "local",
            "desired_status": "active",
            "replicas": 1,
            "config": {},
        },
        headers=ADMIN_HEADERS,
        timeout_seconds=30,
    )
    deployment_id = _required_id(deployment, "deployment")
    checked_steps.append("activation:deployment created")

    task = runner.request_json(
        f"{API_BASE_URL}/v1/deployments/{deployment_id}/tasks",
        payload={
            "input": {"message": "compose smoke activation path"},
            "thread_id": "compose-runtime-smoke",
        },
        headers=ADMIN_HEADERS | {"Idempotency-Key": "compose-runtime-smoke-task"},
        timeout_seconds=30,
    )
    run_id = task.get("run_id")
    task_id = task.get("task_id")
    if run_id is None:
        raise RuntimeError("deployment task response did not include run_id")
    checked_steps.append("activation:deployment task submitted")

    run = _wait_for_terminal_run(runner, run_id, retries, delay_seconds)
    checked_steps.append("activation:run reached terminal state")
    events = runner.get_json(
        f"{API_BASE_URL}/v1/runs/{run_id}/events",
        headers=ADMIN_HEADERS,
        timeout_seconds=30,
    )
    checked_steps.append("activation:run events inspected")
    attempts = runner.get_json(
        f"{API_BASE_URL}/v1/runs/{run_id}/attempts",
        headers=ADMIN_HEADERS,
        timeout_seconds=30,
    )
    checked_steps.append("activation:run attempts inspected")

    return {
        "checked_steps": checked_steps,
        "package_uri": package_uri,
        "agent_id": agent_id,
        "agent_version_id": version_id,
        "deployment_id": deployment_id,
        "task_id": task_id,
        "run_id": run_id,
        "terminal_status": _run_status(run),
        "event_count": len(events) if isinstance(events, list) else 0,
        "attempt_count": len(attempts) if isinstance(attempts, list) else 0,
        "repository_root": str(root),
    }


def _support_agent_manifest() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "name": "support-agent",
        "version": "0.1.0",
        "runtime": {
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:build_graph",
            "python": ">=3.11",
        },
        "capabilities": {
            "invoke": True,
            "stream": True,
            "checkpoint": True,
            "resume": True,
            "interrupt": True,
            "human_in_loop": True,
            "tool_events": True,
            "model_events": True,
            "token_usage": True,
            "filesystem": False,
            "subagents": False,
        },
    }


def _required_id(payload: dict[str, Any], label: str) -> object:
    value = payload.get("id")
    if value is None:
        raise RuntimeError(f"{label} response did not include id")
    return value


def _wait_for_terminal_run(
    runner: RuntimeSmokeRunner,
    run_id: object,
    retries: int,
    delay_seconds: float,
) -> dict[str, Any]:
    last_run: dict[str, Any] | None = None
    for attempt in range(retries):
        run = runner.get_json(
            f"{API_BASE_URL}/v1/runs/{run_id}",
            headers=ADMIN_HEADERS,
            timeout_seconds=30,
        )
        if not isinstance(run, dict):
            raise RuntimeError(f"run {run_id} response was not an object")
        last_run = run
        if _run_status(run) in TERMINAL_RUN_STATUSES:
            return run
        if attempt < retries - 1:
            time.sleep(delay_seconds)
    raise RuntimeError(f"run {run_id} did not reach terminal state: {last_run}")


def _run_status(run: dict[str, Any]) -> str:
    status = run.get("status")
    return str(status or "unknown")


def _write_activation_evidence_index(
    evidence_dir: Path,
    *,
    root: Path,
    evidence: dict[str, Any],
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "workflow: integration.yml",
        "smoke-command: uv run python scripts/compose_runtime_smoke.py",
        "artifact-name: compose-evidence-index",
        "package validation completed",
        "agent version created",
        "deployment created",
        "deployment task submitted",
        "run reached terminal state",
        "console health checked",
        "evidence index written",
    ]
    for key in [
        "package_uri",
        "agent_id",
        "agent_version_id",
        "deployment_id",
        "task_id",
        "run_id",
        "terminal_status",
        "event_count",
        "attempt_count",
    ]:
        lines.append(f"{key}: {evidence.get(key)}")
    content = "\n".join(lines) + "\n"
    (evidence_dir / "compose-evidence-index.txt").write_text(content, encoding="utf-8")


def _ensure_compose_env(root: Path) -> bool:
    env_path = root / ".env"
    if env_path.exists():
        return False
    example_path = root / ".env.example"
    if not example_path.exists():
        raise RuntimeError("Compose smoke requires .env or .env.example at the repository root.")
    shutil.copyfile(example_path, env_path)
    return True


def _backup_restore_smoke(runner: RuntimeSmokeRunner) -> None:
    backup_payload = {
        "plan_id": 9,
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
