import subprocess
import sys
from pathlib import Path


def test_worker_entrypoint_prints_ready_message() -> None:
    project_root = Path(__file__).resolve().parents[2]
    worker_entrypoint = project_root / "apps" / "worker" / "dimoo_run_worker" / "main.py"

    result = subprocess.run(
        [sys.executable, str(worker_entrypoint)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip().startswith("DimooRun worker process ready")
    assert "idle" in result.stdout
