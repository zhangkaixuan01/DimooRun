import subprocess
import sys


def test_openapi_diff_script_accepts_current_checked_in_schema() -> None:
    diff = subprocess.run(
        [sys.executable, "scripts/check_openapi_diff.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert diff.returncode == 0, diff.stderr
    assert "OpenAPI schema is current" in diff.stdout
