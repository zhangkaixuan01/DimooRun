import os
import tempfile
from typing import cast
from uuid import uuid4

from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.replay_jobs import reset_replay_comparisons
from dimoo_run.api.native.runtime import default_native_runtime, reset_native_runtime
from dimoo_run.domain.enums import RunStatus
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.packages.validation import validation_token
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-quality-{uuid4().hex}.db"
    reset_api_key_authenticator()
    reset_replay_comparisons()
    reset_native_runtime()


def create_api_key(*, scopes: set[str] | None = None) -> tuple[str, ServiceAccountRecord]:
    requested_scopes = scopes or {"agent:read", "agent:write", "agent:deploy", "agent:invoke"}
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="quality",
        permissions=requested_scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="quality-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=requested_scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def auth_headers(api_key: str | None = None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key or create_api_key()[0]}",
        "X-Request-Id": "req_quality",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "local",
    }


def admin_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Request-Id": "req_quality",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "local",
    }


def validated_manifest(package_uri: str) -> dict[str, object]:
    manifest: dict[str, object] = {
        "runtime": {
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
        }
    }
    manifest["validation_token"] = validation_token(
        package_uri=package_uri,
        framework="langgraph",
        adapter="langgraph",
        entrypoint="agent:create_agent",
        manifest=manifest,
    )
    return manifest


def create_agent_versions(client: TestClient, key: str) -> tuple[int, int, int]:
    agent = client.post("/v1/agents", headers=auth_headers(key), json={"name": "quality-agent"})
    assert agent.status_code == 201
    agent_id = agent.json()["id"]
    baseline = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "1.0.0",
            "package_uri": "file://quality-agent-v1",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": validated_manifest("file://quality-agent-v1"),
            "status": "ready",
        },
    )
    assert baseline.status_code == 201
    candidate = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "1.1.0",
            "package_uri": "file://quality-agent-v11",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": validated_manifest("file://quality-agent-v11"),
            "status": "ready",
        },
    )
    assert candidate.status_code == 201
    return agent_id, baseline.json()["id"], candidate.json()["id"]


def create_failed_run(client: TestClient, key: str, agent_id: int) -> int:
    task = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"ticket_id": "INC-300", "api_key": "sk-secret"}},
    )
    assert task.status_code == 202
    run_id = cast(int, task.json()["run_id"])
    runtime = default_native_runtime()
    run = runtime.get_run(run_id, tenant_id=1, project_id=1)
    assert run is not None
    run.status = RunStatus.failed
    run.error = {"message": "provider timeout", "api_key": "sk-secret"}
    return run_id


def test_run_capture_redacts_payload_and_deduplicates_by_dataset_and_run() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _, _ = create_agent_versions(client, key)
    run_id = create_failed_run(client, key, agent_id)

    first = client.post(
        "/v1/datasets/capture-run",
        headers=admin_headers(),
        json={
            "dataset_name": "support-regressions",
            "source_run_id": run_id,
            "label": "provider-timeout",
            "redact_fields": ["api_key"],
        },
    )
    second = client.post(
        "/v1/datasets/capture-run",
        headers=admin_headers(),
        json={
            "dataset_name": "support-regressions",
            "source_run_id": run_id,
            "label": "provider-timeout",
            "redact_fields": ["api_key"],
        },
    )

    assert first.status_code == 201
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert second_body["duplicate"] is True
    assert second_body["dataset_item_id"] == first_body["dataset_item_id"]
    assert first_body["dataset_name"] == "support-regressions"
    assert first_body["source_run_id"] == run_id
    assert first_body["redaction"]["fields"] == ["api_key"]
    assert first_body["payload_preview"]["input"]["api_key"] == "[REDACTED]"
    assert first_body["payload_preview"]["error"]["api_key"] == "[REDACTED]"
    assert first_body["provenance"]["source_run_id"] == run_id
    assert first_body["audit"]["action"] == "dataset.capture_run"


def test_experiment_run_returns_scores_and_quality_gate_result() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, baseline_version_id, candidate_version_id = create_agent_versions(client, key)
    run_id = create_failed_run(client, key, agent_id)
    capture = client.post(
        "/v1/datasets/capture-run",
        headers=admin_headers(),
        json={
            "dataset_name": "support-regressions",
            "source_run_id": run_id,
            "label": "provider-timeout",
        },
    )
    assert capture.status_code == 201

    experiment = client.post(
        "/v1/experiments/run",
        headers=admin_headers(),
        json={
            "name": "candidate-quality",
            "agent_id": agent_id,
            "baseline_agent_version_id": baseline_version_id,
            "candidate_agent_version_id": candidate_version_id,
            "dataset_id": capture.json()["dataset_id"],
            "evaluator_config": {"min_score": 0.8, "evaluators": ["exact_match"]},
        },
    )

    assert experiment.status_code == 201
    body = experiment.json()
    assert body["experiment"]["name"] == "candidate-quality"
    assert body["run"]["status"] == "completed"
    assert body["score_distribution"]["count"] == 1
    assert body["score_distribution"]["average_score"] == 1.0
    assert body["results"][0]["evaluator_name"] == "exact_match"
    assert body["results"][0]["passed"] is True
    assert body["quality_gate"]["status"] == "passed"
    assert body["quality_gate"]["promotion_allowed"] is True
    assert body["quality_gate"]["evidence"]["dataset_id"] == capture.json()["dataset_id"]


def test_quality_gate_preview_blocks_failed_experiment_result() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _baseline_version_id, candidate_version_id = create_agent_versions(client, key)
    run_id = create_failed_run(client, key, agent_id)
    capture = client.post(
        "/v1/datasets/capture-run",
        headers=admin_headers(),
        json={"dataset_name": "support-regressions", "source_run_id": run_id},
    )
    assert capture.status_code == 201
    experiment = client.post(
        "/v1/experiments/run",
        headers=admin_headers(),
        json={
            "name": "candidate-quality",
            "agent_id": agent_id,
            "candidate_agent_version_id": candidate_version_id,
            "dataset_id": capture.json()["dataset_id"],
            "evaluator_config": {"min_score": 1.1, "evaluators": ["exact_match"]},
        },
    )
    assert experiment.status_code == 201

    preview = client.post(
        "/v1/quality-gates/preview",
        headers=admin_headers(),
        json={
            "deployment_id": 10,
            "candidate_agent_version_id": candidate_version_id,
            "experiment_run_id": experiment.json()["run"]["id"],
        },
    )

    assert preview.status_code == 200
    body = preview.json()
    assert body["status"] == "failed"
    assert body["promotion_allowed"] is False
    assert body["blocked_reason"] == "quality_gate_failed"
    assert body["required_evidence"] == ["experiment_run", "evaluation_results"]
    assert body["audit"]["action"] == "quality_gate.preview"


def test_quality_gate_preview_blocks_candidate_mismatch() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _baseline_version_id, candidate_version_id = create_agent_versions(client, key)
    other_candidate = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "1.2.0",
            "package_uri": "file://quality-agent-v12",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": validated_manifest("file://quality-agent-v12"),
            "status": "ready",
        },
    )
    assert other_candidate.status_code == 201
    run_id = create_failed_run(client, key, agent_id)
    capture = client.post(
        "/v1/datasets/capture-run",
        headers=admin_headers(),
        json={"dataset_name": "support-regressions", "source_run_id": run_id},
    )
    assert capture.status_code == 201
    experiment = client.post(
        "/v1/experiments/run",
        headers=admin_headers(),
        json={
            "name": "candidate-quality",
            "agent_id": agent_id,
            "candidate_agent_version_id": candidate_version_id,
            "dataset_id": capture.json()["dataset_id"],
            "evaluator_config": {"min_score": 0.8, "evaluators": ["exact_match"]},
        },
    )
    assert experiment.status_code == 201

    preview = client.post(
        "/v1/quality-gates/preview",
        headers=admin_headers(),
        json={
            "deployment_id": 10,
            "candidate_agent_version_id": other_candidate.json()["id"],
            "experiment_run_id": experiment.json()["run"]["id"],
        },
    )

    assert preview.status_code == 200
    body = preview.json()
    assert body["status"] == "failed"
    assert body["promotion_allowed"] is False
    assert body["blocked_reason"] == "candidate_evidence_mismatch"
    assert body["evidence"]["candidate_agent_version_id"] == candidate_version_id
    assert body["evidence"]["requested_candidate_agent_version_id"] == other_candidate.json()["id"]
