from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    return_code: int


def repository_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "apps").exists():
            return candidate
    return current


def compose_command(action: str) -> list[str]:
    if action == "up":
        return ["docker", "compose", "up", "-d"]
    if action == "down":
        return ["docker", "compose", "down"]
    if action == "logs":
        return ["docker", "compose", "logs", "-f"]
    raise ValueError(f"unsupported compose action: {action}")


def run_compose(action: str, *, dry_run: bool = False, cwd: Path | None = None) -> CommandResult:
    command = compose_command(action)
    if dry_run:
        print(" ".join(command))
        return CommandResult(command=command, return_code=0)
    completed = subprocess.run(command, cwd=repository_root(cwd), check=False)
    return CommandResult(command=command, return_code=completed.returncode)
