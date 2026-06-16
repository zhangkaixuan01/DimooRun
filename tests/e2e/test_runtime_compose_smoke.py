import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "compose_runtime_smoke.py"
SPEC = importlib.util.spec_from_file_location("compose_runtime_smoke", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CONSOLE_URL = MODULE.CONSOLE_URL
SERVER_HEALTH_URL = MODULE.SERVER_HEALTH_URL
run_compose_runtime_smoke = MODULE.run_compose_runtime_smoke


class FakeRunner:
    def __init__(self, *, fail_up: bool = False, probe_failures: int = 0) -> None:
        self.fail_up = fail_up
        self.probe_failures = probe_failures
        self.commands: list[list[str]] = []
        self.probed: list[str] = []
        self.requests: list[tuple[str, dict[str, object]]] = []
        self.gets: list[str] = []

    def run(self, command: list[str], timeout_seconds: int) -> None:
        _ = timeout_seconds
        self.commands.append(command)
        if self.fail_up and command[:3] == ["docker", "compose", "up"]:
            raise RuntimeError("compose up failed")

    def probe_url(self, url: str, timeout_seconds: int) -> None:
        _ = timeout_seconds
        self.probed.append(url)
        if self.probe_failures > 0:
            self.probe_failures -= 1
            raise RuntimeError(f"{url} not ready yet")

    def request_json(
        self,
        url: str,
        *,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, object]:
        _ = headers, timeout_seconds
        self.requests.append((url, payload))
        if url.endswith("/v1/packages/validate"):
            return {"ready": True, "validation_token": "validation-token-1"}
        if url.endswith("/v1/agents"):
            return {"id": 101}
        if url.endswith("/v1/agents/101/versions"):
            return {"id": 202, "status": "ready"}
        if url.endswith("/v1/deployments"):
            return {"id": 303, "desired_status": "active"}
        if url.endswith("/v1/deployments/303/tasks"):
            return {"run_id": 404, "task_id": 505, "status": "queued"}
        return {"status": "ready"}

    def get_json(self, url: str, *, headers: dict[str, str], timeout_seconds: int) -> object:
        _ = headers, timeout_seconds
        self.gets.append(url)
        if url.endswith("/v1/runs/404"):
            return {"id": 404, "status": "succeeded", "task_id": 505}
        if url.endswith("/v1/runs/404/events"):
            return [{"type": "attempt.started"}, {"type": "run.succeeded"}]
        if url.endswith("/v1/runs/404/attempts"):
            return [{"id": 606, "status": "succeeded", "attempt_no": 1}]
        raise AssertionError(f"unexpected GET {url}")


def test_compose_runtime_smoke_requires_activation_path_steps() -> None:
    script = MODULE_PATH.read_text(encoding="utf-8")
    required_markers = [
        "package validation completed",
        "agent version created",
        "deployment created",
        "deployment task submitted",
        "run reached terminal state",
        "console health checked",
        "evidence index written",
    ]
    for marker in required_markers:
        assert marker in script


def test_runtime_compose_smoke_runs_compose_and_probes_server_and_console(tmp_path: Path) -> None:
    runner = FakeRunner(probe_failures=1)
    evidence_dir = tmp_path / "compose-diagnostics"

    result = run_compose_runtime_smoke(
        Path("."),
        runner=runner,
        evidence_dir=evidence_dir,
        retries=3,
        probe_delay_seconds=0,
    )

    assert result.ok is True
    assert runner.commands == [
        ["docker", "compose", "config", "--quiet"],
        ["docker", "compose", "up", "--build", "--detach", "--wait"],
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
        ["docker", "compose", "ps"],
        ["docker", "compose", "down", "--remove-orphans", "--volumes"],
    ]
    assert SERVER_HEALTH_URL in runner.probed
    assert CONSOLE_URL in runner.probed
    assert [step for step in result.checked_steps if step.startswith("activation:")] == [
        "activation:console health checked",
        "activation:package validation completed",
        "activation:agent version created",
        "activation:deployment created",
        "activation:deployment task submitted",
        "activation:run reached terminal state",
        "activation:run events inspected",
        "activation:run attempts inspected",
        "activation:evidence index written",
    ]
    assert runner.requests[0][0].endswith("/v1/packages/validate")
    assert runner.requests[4][0].endswith("/v1/deployments/303/tasks")
    assert runner.requests[5][1]["plan_id"] == 9
    assert runner.requests[5][1]["targets"] == ["runs", "datasets", "audit_logs"]
    assert runner.requests[6][1]["confirmation"] == "RESTORE PROJECT 1"
    assert any(url.endswith("/v1/runs/404") for url in runner.gets)
    assert any(url.endswith("/v1/runs/404/events") for url in runner.gets)
    assert any(url.endswith("/v1/runs/404/attempts") for url in runner.gets)
    evidence = (evidence_dir / "compose-evidence-index.txt").read_text(encoding="utf-8")
    assert "agent_id: 101" in evidence
    assert "agent_version_id: 202" in evidence
    assert "deployment_id: 303" in evidence
    assert "run_id: 404" in evidence
    assert "terminal_status: succeeded" in evidence


def test_runtime_compose_smoke_records_failure_and_still_tears_down() -> None:
    runner = FakeRunner(fail_up=True)

    result = run_compose_runtime_smoke(Path("."), runner=runner, retries=1, probe_delay_seconds=0)

    assert result.ok is False
    assert "compose up failed" in result.errors[0]
    assert runner.commands[-1] == ["docker", "compose", "down", "--remove-orphans", "--volumes"]


def test_runtime_compose_smoke_fails_fast_when_package_validation_is_not_ready() -> None:
    class InvalidValidationRunner(FakeRunner):
        def request_json(
            self,
            url: str,
            *,
            payload: dict[str, object],
            headers: dict[str, str],
            timeout_seconds: int,
        ) -> dict[str, object]:
            if url.endswith("/v1/packages/validate"):
                return {
                    "ready": False,
                    "status": "invalid",
                    "errors": [{"code": "unsupported_capability"}],
                    "validation_token": None,
                }
            return super().request_json(
                url,
                payload=payload,
                headers=headers,
                timeout_seconds=timeout_seconds,
            )

    runner = InvalidValidationRunner()

    result = run_compose_runtime_smoke(Path("."), runner=runner, retries=1, probe_delay_seconds=0)

    assert result.ok is False
    assert "package validation did not succeed" in result.errors[0]
    assert runner.commands[-1] == ["docker", "compose", "down", "--remove-orphans", "--volumes"]
