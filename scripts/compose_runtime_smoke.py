from __future__ import annotations

import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

SERVER_HEALTH_URL = "http://127.0.0.1:8000/healthz"
CONSOLE_URL = "http://127.0.0.1:5173/"


@dataclass(frozen=True)
class ComposeRuntimeSmokeResult:
    errors: list[str] = field(default_factory=list)

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


class RuntimeSmokeRunner(Protocol):
    def run(self, command: list[str], timeout_seconds: int) -> None: ...

    def probe_url(self, url: str, timeout_seconds: int) -> None: ...


def run_compose_runtime_smoke(
    root: Path,
    *,
    runner: RuntimeSmokeRunner | None = None,
    retries: int = 30,
    probe_delay_seconds: float = 2.0,
) -> ComposeRuntimeSmokeResult:
    active_runner = runner or ComposeRuntimeRunner(root)
    errors: list[str] = []

    try:
        active_runner.run(["docker", "compose", "config", "--quiet"], 60)
        active_runner.run(["docker", "compose", "up", "--build", "--detach"], 900)
        _wait_for_url(active_runner, SERVER_HEALTH_URL, retries, probe_delay_seconds)
        _wait_for_url(active_runner, CONSOLE_URL, retries, probe_delay_seconds)
        active_runner.run(["docker", "compose", "ps"], 60)
    except Exception as exc:
        errors.append(str(exc))
    finally:
        try:
            active_runner.run(["docker", "compose", "down", "--remove-orphans"], 300)
        except Exception as exc:
            errors.append(f"teardown failed: {exc}")

    return ComposeRuntimeSmokeResult(errors=errors)


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
    print("Compose runtime smoke passed.")


if __name__ == "__main__":
    main()
