import json
import subprocess
import sys
from pathlib import Path

from dimoo_run.server import create_app


def test_openapi_schema_contains_error_response_and_runtime_control_paths() -> None:
    schema = create_app().openapi()

    assert "ErrorResponse" in schema["components"]["schemas"]
    assert "/v1/deployments/{deployment_id}/activate" in schema["paths"]
    assert "/v1/deployments/{deployment_id}/instances" in schema["paths"]
    assert "/v1/human-tasks/{task_id}/approve" in schema["paths"]


def test_export_openapi_script_writes_contract_file() -> None:
    output_path = Path("openapi/dimoorun.openapi.json")
    if output_path.exists():
        output_path.unlink()

    result = subprocess.run(
        [sys.executable, "scripts/export_openapi.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    schema = json.loads(output_path.read_text(encoding="utf-8"))
    assert schema["info"]["title"] == "DimooRun API"
    assert "/v1/agents/{agent_id}/invoke" in schema["paths"]
