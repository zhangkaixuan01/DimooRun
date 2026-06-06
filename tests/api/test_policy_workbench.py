import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import reset_api_key_authenticator
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DIMOORUN_DEV_API_KEY"] = "dev-local-key"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-policy-workbench-{uuid4().hex}.db"
    reset_api_key_authenticator()


def admin_headers(request_id: str = "req_policy_workbench") -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "local",
        "X-Request-Id": request_id,
    }


def draft_policy(**overrides: object) -> dict[str, object]:
    policy: dict[str, object] = {
        "name": "deny-prod-delete",
        "type": "approval",
        "resource_type": "deployment",
        "action": "delete",
        "decision": "deny",
        "priority": 10,
        "risk_level": "critical",
        "condition": {"environment": "prod"},
        "reason": "Production deletion requires a separate approval path.",
    }
    policy.update(overrides)
    return policy


def test_policy_simulation_returns_decision_audit_preview_and_conflicts() -> None:
    client = TestClient(create_app())

    existing = client.post(
        "/v1/policies",
        headers=admin_headers("req_existing_policy"),
        json=draft_policy(
            name="existing-allow",
            decision="allow",
            priority=10,
            reason="Existing allow",
        ),
    )
    assert existing.status_code == 201

    simulated = client.post(
        "/v1/policies/simulate",
        headers=admin_headers("req_policy_simulate"),
        json={
            "draft_policy": draft_policy(),
            "sample": {
                "resource_type": "deployment",
                "resource_id": 42,
                "action": "delete",
                "environment": "prod",
                "attributes": {"owner": "runtime"},
            },
        },
    )

    assert simulated.status_code == 200
    body = simulated.json()
    assert body["decision"]["result"] == "deny"
    assert body["decision"]["policy_name"] == "deny-prod-delete"
    assert body["matched_resources"] == [
        {
            "resource_type": "deployment",
            "resource_id": 42,
            "action": "delete",
            "environment": "prod",
        }
    ]
    assert body["audit_preview"]["action"] == "policy.simulate"
    assert body["audit_preview"]["resource_type"] == "deployment"
    assert body["conflict_warnings"][0]["code"] == "priority_conflict"
    assert body["conflict_warnings"][0]["conflicting_policy_id"] == existing.json()["item"]["id"]


def test_policy_activation_versions_policy_and_rolls_back() -> None:
    client = TestClient(create_app())

    activated = client.post(
        "/v1/policies/activate",
        headers=admin_headers("req_policy_activate"),
        json={
            "draft_policy": draft_policy(name="protect-prod-delete", decision="deny"),
            "audit_reason": "Block accidental production deletion.",
        },
    )

    assert activated.status_code == 201
    active_body = activated.json()
    assert active_body["item"]["name"] == "protect-prod-delete"
    assert active_body["item"]["status"] == "active"
    assert active_body["version"] == 1
    assert active_body["audit"]["reason"] == "Block accidental production deletion."
    assert active_body["rollback_target"]["policy_id"] == active_body["item"]["id"]

    updated = client.post(
        "/v1/policies/activate",
        headers=admin_headers("req_policy_activate_v2"),
        json={
            "draft_policy": draft_policy(
                name="protect-prod-delete",
                decision="require_approval",
                reason="Route production deletion to approvers.",
            ),
            "audit_reason": "Switch to explicit approval.",
        },
    )
    assert updated.status_code == 201
    assert updated.json()["version"] == 2
    assert updated.json()["item"]["decision"] == "require_approval"

    rolled_back = client.post(
        f"/v1/policies/{active_body['item']['id']}/rollback",
        headers=admin_headers("req_policy_rollback"),
        json={
            "target_version": 1,
            "audit_reason": "Restore deny while approval queue is reviewed.",
        },
    )

    assert rolled_back.status_code == 200
    rollback_body = rolled_back.json()
    assert rollback_body["item"]["decision"] == "deny"
    assert rollback_body["version"] == 3
    assert rollback_body["rollback_target"]["version"] == 1
    assert rollback_body["audit"]["reason"] == "Restore deny while approval queue is reviewed."


def test_policy_activation_requires_audit_reason() -> None:
    client = TestClient(create_app())

    activated = client.post(
        "/v1/policies/activate",
        headers=admin_headers("req_policy_activate_missing_reason"),
        json={"draft_policy": draft_policy(name="protect-prod-delete", decision="deny")},
    )

    assert activated.status_code == 400
    assert activated.json()["error_code"] == "audit_reason_required"
    assert activated.json()["details"]["field"] == "audit_reason"


def test_policy_rollback_requires_audit_reason() -> None:
    client = TestClient(create_app())
    activated = client.post(
        "/v1/policies/activate",
        headers=admin_headers("req_policy_activate_for_rollback_reason"),
        json={
            "draft_policy": draft_policy(name="protect-prod-delete", decision="deny"),
            "audit_reason": "Initial governance decision.",
        },
    )
    assert activated.status_code == 201

    rolled_back = client.post(
        f"/v1/policies/{activated.json()['item']['id']}/rollback",
        headers=admin_headers("req_policy_rollback_missing_reason"),
        json={"target_version": 1},
    )

    assert rolled_back.status_code == 400
    assert rolled_back.json()["error_code"] == "audit_reason_required"
    assert rolled_back.json()["details"]["field"] == "audit_reason"


def test_human_task_decision_preserves_context_comment_and_resume_outcome() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/v1/human-tasks",
        headers=admin_headers("req_human_task_create"),
        json={
            "name": "run-approval-77",
            "source": "deployment:checkout-prod",
            "risk": "critical",
            "status": "pending",
            "assignee": "platform-approver",
            "requester": "deploy-bot",
            "risk_reason": "Policy denied direct production promotion.",
            "decision_context": {"run_id": 77, "deployment_id": 13},
            "diff": {"desired_status": {"from": "paused", "to": "active"}},
        },
    )
    assert created.status_code == 201
    task_id = created.json()["item"]["id"]

    decided = client.post(
        f"/v1/human-tasks/{task_id}/reject",
        headers=admin_headers("req_human_task_reject"),
        json={
            "decision_payload": {
                "comment": "Candidate version has a replay regression.",
                "decided_by": "ops@example.com",
            }
        },
    )

    assert decided.status_code == 200
    item = decided.json()["item"]
    assert item["status"] == "rejected"
    assert item["requester"] == "deploy-bot"
    assert item["risk_reason"] == "Policy denied direct production promotion."
    assert item["decision_context"] == {"run_id": 77, "deployment_id": 13}
    assert item["diff"] == {"desired_status": {"from": "paused", "to": "active"}}
    assert item["decision"]["comment"] == "Candidate version has a replay regression."
    assert item["resume_outcome"]["status"] == "blocked"
    assert item["resume_outcome"]["task_id"] == task_id
