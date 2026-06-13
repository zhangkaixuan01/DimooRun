import os
import tempfile
from typing import cast
from uuid import uuid4

from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.deployments import default_deployment_control, reset_deployment_control
from dimoo_run.api.native.runtime import reset_native_runtime
from dimoo_run.deployments.service import StaticPolicyEngine
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.packages.validation import validation_token
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-promotion-{uuid4().hex}.db"
    reset_api_key_authenticator()
    reset_deployment_control()
    reset_native_runtime()


def create_api_key(*, scopes: set[str] | None = None) -> tuple[str, ServiceAccountRecord]:
    requested_scopes = scopes or {"agent:read", "agent:write", "agent:deploy", "agent:invoke"}
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="promotion",
        permissions=requested_scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="promotion-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=requested_scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def auth_headers(api_key: str, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": "req_promotion",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def admin_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Request-Id": "req_promotion_quality",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "local",
    }


def validated_manifest(
    *,
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


def create_agent_version(
    client: TestClient,
    key: str,
    agent_id: int,
    *,
    version: str,
    package_uri: str,
    status: str = "ready",
) -> dict[str, object]:
    response = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": version,
            "package_uri": package_uri,
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": validated_manifest(package_uri=package_uri),
            "status": status,
        },
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def create_deployment_fixture(
    client: TestClient,
    key: str,
) -> tuple[int, dict[str, object], dict[str, object], dict[str, object]]:
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(key),
        json={"name": "support-agent"},
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]
    current = create_agent_version(
        client,
        key,
        agent_id,
        version="1.0.0",
        package_uri="file://support-agent-v1",
    )
    candidate = create_agent_version(
        client,
        key,
        agent_id,
        version="1.1.0",
        package_uri="file://support-agent-v11",
    )
    deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key),
        json={
            "agent_id": agent_id,
            "agent_version_id": current["id"],
            "environment": "production",
            "desired_status": "active",
            "replicas": 2,
        },
    )
    assert deployment.status_code == 201
    return agent_id, current, candidate, cast(dict[str, object], deployment.json())


def create_quality_gate_evidence(
    client: TestClient,
    *,
    agent_id: int,
    candidate_version_id: int,
    source_run_id: int,
    minimum_score: float = 0.8,
) -> int:
    capture = client.post(
        "/v1/datasets/capture-run",
        headers=admin_headers(),
        json={
            "dataset_name": "promotion-quality",
            "source_run_id": source_run_id,
            "label": "pre-promotion",
        },
    )
    assert capture.status_code == 201
    experiment = client.post(
        "/v1/experiments/run",
        headers=admin_headers(),
        json={
            "name": "promotion-quality",
            "agent_id": agent_id,
            "candidate_agent_version_id": candidate_version_id,
            "dataset_id": capture.json()["dataset_id"],
            "evaluator_config": {"min_score": minimum_score, "evaluators": ["exact_match"]},
        },
    )
    assert experiment.status_code == 201
    return cast(int, experiment.json()["run"]["id"])


def test_deployment_promotion_preview_reports_impact_and_rollback_context() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, current, candidate, deployment = create_deployment_fixture(client, key)
    task = client.post(
        f"/v1/deployments/{deployment['id']}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "queued before promotion"}},
    )
    assert task.status_code == 202
    experiment_run_id = create_quality_gate_evidence(
        client,
        agent_id=agent_id,
        candidate_version_id=cast(int, candidate["id"]),
        source_run_id=task.json()["run_id"],
    )

    preview = client.get(
        f"/v1/deployments/{deployment['id']}/promotion-preview",
        headers=auth_headers(key),
        params={
            "candidate_version_id": cast(int, candidate["id"]),
            "experiment_run_id": experiment_run_id,
        },
    )

    assert preview.status_code == 200
    body = preview.json()
    assert body["deployment_id"] == deployment["id"]
    assert body["current_agent_version_id"] == current["id"]
    assert body["candidate_agent_version_id"] == candidate["id"]
    assert body["desired_status"] == "active"
    assert body["runtime_status"] == "not_loaded"
    assert body["active_runs"] == 1
    assert body["queued_tasks"] == 1
    assert body["candidate_validation_status"] == "ready"
    assert body["rollback_agent_version_id"] == current["id"]
    assert body["required_permissions"] == ["agent:deploy"]
    assert body["audit_required"] is True
    assert body["can_promote"] is True
    assert body["blocked_reason"] is None
    assert body["quality_gate"]["status"] == "passed"
    assert body["quality_gate"]["evidence"]["experiment_run_id"] == experiment_run_id
    assert "active_runs_will_continue_on_current_version" in body["warnings"]
    assert "queued_tasks_will_use_current_version" in body["warnings"]


def test_deployment_promote_and_rollback_persist_audit_context() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, current, candidate, deployment = create_deployment_fixture(client, key)
    task = client.post(
        f"/v1/deployments/{deployment['id']}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "promotion quality evidence"}},
    )
    assert task.status_code == 202
    experiment_run_id = create_quality_gate_evidence(
        client,
        agent_id=agent_id,
        candidate_version_id=cast(int, candidate["id"]),
        source_run_id=task.json()["run_id"],
    )

    promoted = client.post(
        f"/v1/deployments/{deployment['id']}/promote",
        headers=auth_headers(key, idempotency_key="promote-1"),
        json={
            "candidate_version_id": candidate["id"],
            "expected_current_version_id": current["id"],
            "experiment_run_id": experiment_run_id,
            "rollout_reason": "ship validated support improvements",
        },
    )

    assert promoted.status_code == 200
    promoted_body = promoted.json()
    assert promoted_body["agent_version_id"] == candidate["id"]
    assert promoted_body["config"]["promotion"]["previous_agent_version_id"] == current["id"]
    assert (
        promoted_body["config"]["promotion"]["rollout_reason"]
        == "ship validated support improvements"
    )
    assert promoted_body["config"]["promotion"]["experiment_run_id"] == experiment_run_id
    assert promoted_body["config"]["promotion"]["quality_gate"]["status"] == "passed"

    rollback = client.post(
        f"/v1/deployments/{deployment['id']}/rollback",
        headers=auth_headers(key, idempotency_key="rollback-1"),
        json={
            "expected_current_version_id": candidate["id"],
            "rollback_reason": "candidate regression",
        },
    )

    assert rollback.status_code == 200
    rollback_body = rollback.json()
    assert rollback_body["agent_version_id"] == current["id"]
    assert rollback_body["config"]["promotion"]["rollback_reason"] == "candidate regression"
    actions = [entry.action for entry in default_deployment_control().audit_sink.entries]
    assert "deployment.promote" in actions
    assert "deployment.rollback" in actions


def test_deployment_promote_rejects_stale_expected_version() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, _current, candidate, deployment = create_deployment_fixture(client, key)
    task = client.post(
        f"/v1/deployments/{deployment['id']}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "promotion quality evidence"}},
    )
    assert task.status_code == 202
    experiment_run_id = create_quality_gate_evidence(
        client,
        agent_id=agent_id,
        candidate_version_id=cast(int, candidate["id"]),
        source_run_id=task.json()["run_id"],
    )

    stale = client.post(
        f"/v1/deployments/{deployment['id']}/promote",
        headers=auth_headers(key),
        json={
            "candidate_version_id": candidate["id"],
            "expected_current_version_id": 999_999,
            "experiment_run_id": experiment_run_id,
            "rollout_reason": "stale operator tab",
        },
    )

    assert stale.status_code == 409
    assert stale.json()["error_code"] == "deployment_version_conflict"


def test_deployment_promote_respects_policy_denial() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, current, candidate, deployment = create_deployment_fixture(client, key)
    default_deployment_control().policy_engine = StaticPolicyEngine(
        allowed=False,
        reason="production freeze",
    )
    task = client.post(
        f"/v1/deployments/{deployment['id']}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "promotion quality evidence"}},
    )
    assert task.status_code == 202
    experiment_run_id = create_quality_gate_evidence(
        client,
        agent_id=agent_id,
        candidate_version_id=cast(int, candidate["id"]),
        source_run_id=task.json()["run_id"],
    )

    denied = client.post(
        f"/v1/deployments/{deployment['id']}/promote",
        headers=auth_headers(key),
        json={
            "candidate_version_id": candidate["id"],
            "expected_current_version_id": current["id"],
            "experiment_run_id": experiment_run_id,
            "rollout_reason": "blocked during freeze",
        },
    )

    assert denied.status_code == 403
    assert denied.json()["error_code"] == "policy_denied"
    assert denied.json()["message"] == "production freeze"


def test_deployment_promote_rejects_missing_or_failed_quality_evidence() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, current, candidate, deployment = create_deployment_fixture(client, key)
    task = client.post(
        f"/v1/deployments/{deployment['id']}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": "promotion quality evidence"}},
    )
    assert task.status_code == 202
    failed_experiment_run_id = create_quality_gate_evidence(
        client,
        agent_id=agent_id,
        candidate_version_id=cast(int, candidate["id"]),
        source_run_id=task.json()["run_id"],
        minimum_score=1.1,
    )

    missing = client.post(
        f"/v1/deployments/{deployment['id']}/promote",
        headers=auth_headers(key),
        json={
            "candidate_version_id": candidate["id"],
            "expected_current_version_id": current["id"],
            "experiment_run_id": 0,
            "rollout_reason": "no evidence",
        },
    )
    assert missing.status_code == 409
    assert missing.json()["error_code"] == "quality_evidence_required"

    failed = client.post(
        f"/v1/deployments/{deployment['id']}/promote",
        headers=auth_headers(key),
        json={
            "candidate_version_id": candidate["id"],
            "expected_current_version_id": current["id"],
            "experiment_run_id": failed_experiment_run_id,
            "rollout_reason": "failed evidence",
        },
    )

    assert failed.status_code == 409
    assert failed.json()["error_code"] == "quality_gate_failed"
