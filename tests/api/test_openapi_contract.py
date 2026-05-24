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


def test_unimplemented_get_routes_document_501_response() -> None:
    schema = create_app().openapi()
    get_paths = [
        "/v1/agents",
        "/v1/agents/{agent_id}",
        "/v1/agents/{agent_id}/versions",
        "/v1/agents/{agent_id}/versions/{version}",
        "/v1/deployments",
        "/v1/deployments/{deployment_id}",
        "/v1/deployments/{deployment_id}/instances",
        "/v1/runs/{run_id}",
        "/v1/runs/{run_id}/events",
        "/v1/runs/{run_id}/attempts",
        "/v1/tasks/{task_id}",
        "/v1/policies",
        "/v1/artifacts/{artifact_id}",
        "/v1/human-tasks",
        "/v1/catalog/items",
    ]

    for path in get_paths:
        operation = schema["paths"][path]["get"]
        assert "501" in operation["responses"], path


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


def test_export_openapi_script_can_write_to_explicit_output(tmp_path) -> None:  # type: ignore[no-untyped-def]
    output_path = tmp_path / "dimoorun.openapi.json"

    result = subprocess.run(
        [sys.executable, "scripts/export_openapi.py", "--output", str(output_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    schema = json.loads(output_path.read_text(encoding="utf-8"))
    assert schema["info"]["title"] == "DimooRun API"
