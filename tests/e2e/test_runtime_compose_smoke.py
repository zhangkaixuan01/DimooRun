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
        return {"status": "ready"}


def test_runtime_compose_smoke_runs_compose_and_probes_server_and_console() -> None:
    runner = FakeRunner(probe_failures=1)

    result = run_compose_runtime_smoke(
        Path("."),
        runner=runner,
        retries=3,
        probe_delay_seconds=0,
    )

    assert result.ok is True
    assert runner.commands == [
        ["docker", "compose", "config", "--quiet"],
        ["docker", "compose", "up", "--build", "--detach"],
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
        ["docker", "compose", "down", "--remove-orphans"],
    ]
    assert SERVER_HEALTH_URL in runner.probed
    assert CONSOLE_URL in runner.probed
    assert len(runner.requests) == 2
    assert runner.requests[0][1]["targets"] == ["runs", "datasets", "audit_logs"]
    assert runner.requests[1][1]["confirmation"] == "RESTORE PROJECT 1"


def test_runtime_compose_smoke_records_failure_and_still_tears_down() -> None:
    runner = FakeRunner(fail_up=True)

    result = run_compose_runtime_smoke(Path("."), runner=runner, retries=1, probe_delay_seconds=0)

    assert result.ok is False
    assert "compose up failed" in result.errors[0]
    assert runner.commands[-1] == ["docker", "compose", "down", "--remove-orphans"]
