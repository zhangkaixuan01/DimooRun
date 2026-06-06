import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import (
    default_api_key_authenticator,
    reset_api_key_authenticator,
)
from dimoo_run.api.native.replay_jobs import reset_replay_comparisons
from dimoo_run.api.native.runtime import default_native_runtime, reset_native_runtime
from dimoo_run.domain.enums import RunStatus
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.packages.validation import validation_token
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-replay-{uuid4().hex}.db"
    reset_api_key_authenticator()
    reset_replay_comparisons()
    reset_native_runtime()


def create_api_key(*, scopes: set[str] | None = None) -> tuple[str, ServiceAccountRecord]:
    requested_scopes = scopes or {"agent:read", "agent:write", "agent:invoke"}
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="replay",
        permissions=requested_scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="replay-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=requested_scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def auth_headers(api_key: str | None = None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key or create_api_key()[0]}",
        "X-Request-Id": "req_replay",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
    }


def validated_manifest(
    package_uri: str,
    entrypoint: str = "agent:create_agent",
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "runtime": {
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": entrypoint,
        }
    }
    manifest["validation_token"] = validation_token(
        package_uri=package_uri,
        framework="langgraph",
        adapter="langgraph",
        entrypoint=entrypoint,
        manifest=manifest,
    )
    return manifest


def create_agent_with_versions(
    client: TestClient,
    key: str,
    *,
    candidate_status: str = "ready",
) -> tuple[int, int, int]:
    agent = client.post("/v1/agents", headers=auth_headers(key), json={"name": "triage-agent"})
    assert agent.status_code == 201
    agent_id = agent.json()["id"]
    source = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "1.0.0",
            "package_uri": "file://triage-agent-v1",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": validated_manifest("file://triage-agent-v1"),
            "status": "ready",
        },
    )
    assert source.status_code == 201
    candidate = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "1.1.0",
            "package_uri": "file://triage-agent-v11",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": validated_manifest("file://triage-agent-v11"),
            "status": candidate_status,
        },
    )
    assert candidate.status_code == 201
    return agent_id, source.json()["id"], candidate.json()["id"]


def test_replay_comparison_creates_replay_with_diff_and_provenance() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _, candidate_version_id = create_agent_with_versions(client, key)
    source_task = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"ticket_id": "INC-101", "message": "provider timeout"}},
    )
    assert source_task.status_code == 202
    source_run_id = source_task.json()["run_id"]
    runtime = default_native_runtime()
    source_run = runtime.get_run(source_run_id, tenant_id=1, project_id=1)
    assert source_run is not None
    source_run.status = RunStatus.failed
    source_run.error = {"message": "provider timeout", "provider": "llm-a"}

    response = client.post(
        "/v1/replay-jobs/compare",
        headers=auth_headers(key),
        json={
            "source_run_id": source_run_id,
            "candidate_agent_version_id": candidate_version_id,
            "replay_config": {"temperature": 0, "dataset_label": "incident-triage"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_run"]["id"] == source_run_id
    assert body["replay_run"]["id"] != source_run_id
    assert body["replay_run"]["agent_version_id"] == candidate_version_id
    assert body["input_diff"]["changed"] is False
    assert body["error_diff"]["changed"] is True
    assert body["event_diff"]["source_count"] >= 2
    assert body["event_diff"]["replay_count"] >= 3
    assert body["latency_delta_ms"] is None
    assert body["provenance"]["source_run_id"] == source_run_id
    assert body["provenance"]["replay_run_id"] == body["replay_run"]["id"]
    assert body["provenance"]["candidate_agent_version_id"] == candidate_version_id
    assert body["provenance"]["replay_config"] == {
        "temperature": 0,
        "dataset_label": "incident-triage",
    }


def test_replay_comparison_rejects_candidate_version_that_is_not_ready() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _, candidate_version_id = create_agent_with_versions(client, key)
    source_task = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"ticket_id": "INC-150", "message": "candidate not ready"}},
    )
    assert source_task.status_code == 202
    draft_candidate = client.patch(
        f"/v1/agents/{agent_id}/versions/1.1.0",
        headers=auth_headers(key),
        json={"status": "draft"},
    )
    assert draft_candidate.status_code == 200

    response = client.post(
        "/v1/replay-jobs/compare",
        headers=auth_headers(key),
        json={
            "source_run_id": source_task.json()["run_id"],
            "candidate_agent_version_id": candidate_version_id,
            "replay_config": {"temperature": 0},
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "agent_version_not_ready"
    assert response.json()["details"]["status"] == "draft"


def test_replay_comparison_dataset_capture_preserves_source_and_replay_ids() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _, candidate_version_id = create_agent_with_versions(client, key)
    source_task = client.post(
        f"/v1/agents/{agent_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"ticket_id": "INC-202"}},
    )
    assert source_task.status_code == 202
    comparison = client.post(
        "/v1/replay-jobs/compare",
        headers=auth_headers(key),
        json={
            "source_run_id": source_task.json()["run_id"],
            "candidate_agent_version_id": candidate_version_id,
            "replay_config": {"dataset_label": "quality-regression"},
        },
    )
    assert comparison.status_code == 201

    capture = client.post(
        f"/v1/replay-jobs/{comparison.json()['comparison_id']}/dataset-captures",
        headers=auth_headers(key),
        json={"dataset_name": "support-regressions", "label": "provider-timeout"},
    )

    assert capture.status_code == 201
    capture_body = capture.json()
    assert capture_body["dataset_name"] == "support-regressions"
    assert capture_body["label"] == "provider-timeout"
    assert capture_body["source_run_id"] == comparison.json()["source_run"]["id"]
    assert capture_body["replay_run_id"] == comparison.json()["replay_run"]["id"]
    assert capture_body["provenance"]["comparison_id"] == comparison.json()["comparison_id"]
