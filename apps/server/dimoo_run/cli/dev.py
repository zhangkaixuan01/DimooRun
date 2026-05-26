from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from dimoo_run.cli.compose import repository_root


@dataclass(frozen=True)
class DevCommand:
    name: str
    command: list[str]
    cwd: Path


def dev_commands(root: Path | None = None) -> list[DevCommand]:
    resolved_root = repository_root(root)
    return [
        DevCommand(
            name="server",
            command=[
                "uv",
                "run",
                "uvicorn",
                "dimoo_run.server:app",
                "--reload",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=resolved_root,
        ),
        DevCommand(
            name="worker",
            command=["uv", "run", "dimoorun", "worker"],
            cwd=resolved_root,
        ),
        DevCommand(
            name="console",
            command=["npm", "run", "dev", "--", "--host", "127.0.0.1"],
            cwd=resolved_root / "apps" / "console",
        ),
    ]


def run_dev(*, dry_run: bool = False, root: Path | None = None) -> int:
    commands = dev_commands(root)
    if dry_run:
        for command in commands:
            print(f"{command.name}: {' '.join(command.command)}")
        return 0
    processes = [subprocess.Popen(command.command, cwd=command.cwd) for command in commands]
    try:
        return max(process.wait() for process in processes)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
