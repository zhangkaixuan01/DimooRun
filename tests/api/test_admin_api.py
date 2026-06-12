import importlib
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from _pytest.monkeypatch import MonkeyPatch
from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.domain.models import (
    Agent,
    AgentVersion,
    AlertRule,
    Deployment,
    HumanTask,
    IngressRoute,
    ObservabilityExporter,
    Policy,
    PublishedSurface,
    SandboxPolicy,
)
from dimoo_run.persistence.database import Base, create_session_factory
from dimoo_run.server import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

ADMIN_PATHS = [
    "/v1/policies",
    "/v1/policies/simulate",
    "/v1/policies/activate",
    "/v1/policies/{policy_id}/rollback",
    "/v1/artifacts/{artifact_id}",
    "/v1/human-tasks",
    "/v1/human-tasks/{task_id}/approve",
    "/v1/human-tasks/{task_id}/reject",
    "/v1/model-gateways",
    "/v1/published-surfaces",
    "/v1/ingress-routes",
    "/v1/catalog/items",
    "/v1/datasets",
    "/v1/experiments",
    "/v1/schedules",
    "/v1/batch-runs",
    "/v1/notifications/channels",
    "/v1/alerts/rules",
    "/v1/backups/plans",
    "/v1/backups/restore-jobs",
    "/v1/webhooks/subscriptions",
    "/v1/incidents",
    "/v1/incidents/{incident_id}/acknowledge",
    "/v1/incidents/{incident_id}/resolve",
    "/v1/identity/tenants",
    "/v1/identity/projects",
    "/v1/identity/environments",
    "/v1/identity/users",
    "/v1/identity/operators",
    "/v1/identity/roles",
    "/v1/identity/permissions",
    "/v1/secrets",
    "/v1/tools",
    "/v1/assets/prompts",
    "/v1/assets/configs",
    "/v1/assets/templates",
    "/v1/audit-logs",
    "/v1/evaluations/results",
    "/v1/feedback",
    "/v1/semantic-store/providers",
    "/v1/observability/exporters",
    "/v1/sandbox/policies",
    "/v1/container-pool/policies",
]


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DIMOORUN_DEV_API_KEY"] = "dev-local-key"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-admin-{uuid4().hex}.db"
    reset_api_key_authenticator()


def admin_headers(request_id: str = "req_admin") -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "local",
        "X-Request-Id": request_id,
    }


def scoped_admin_headers(
    request_id: str,
    *,
    tenant_id: int = 1,
    project_id: int = 1,
    environment: str = "local",
) -> dict[str, str]:
    headers = admin_headers(request_id)
    headers["X-Tenant-Id"] = str(tenant_id)
    headers["X-Project-Id"] = str(project_id)
    headers["X-Environment"] = environment
    return headers


def test_admin_api_paths_are_registered_in_openapi() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in ADMIN_PATHS:
        assert path in paths


def test_high_risk_admin_action_marks_audit_required() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/human-tasks/1/approve",
        headers=admin_headers("req_approve"),
        json={"decision_payload": {"approved": True}},
    )

    assert response.status_code == 200
    assert response.json()["audit_required"] is True
    assert response.json()["item"]["status"] == "approved"


def test_admin_collection_api_supports_minimal_create_and_list() -> None:
    client = TestClient(create_app())

    created = client.post(
        "/v1/policies",
        headers=admin_headers("req_admin_write"),
        json={"name": "allow-read", "metadata": {"scope": "project"}},
    )
    listed = client.get("/v1/policies", headers=admin_headers("req_admin_read"))

    assert created.status_code == 201
    assert created.json()["item"]["name"] == "allow-read"
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1
    assert any(item["name"] == "allow-read" for item in listed.json()["items"])

    resource_id = created.json()["item"]["id"]
    updated = client.patch(
        f"/v1/policies/{resource_id}",
        headers=admin_headers("req_admin_update"),
        json={"name": "allow-read-updated", "status": "disabled"},
    )
    deleted = client.delete(
        f"/v1/policies/{resource_id}",
        headers=admin_headers("req_admin_delete"),
    )

    assert updated.status_code == 200
    assert updated.json()["item"]["name"] == "allow-read-updated"
    assert updated.json()["item"]["status"] == "disabled"
    assert deleted.status_code == 200
    assert deleted.json()["item"]["status"] == "deleted"


def test_admin_collections_are_isolated_by_request_scope() -> None:
    client = TestClient(create_app())
    name = f"scoped-policy-{uuid4().hex[:8]}"

    created = client.post(
        "/v1/policies",
        headers=scoped_admin_headers("req_scoped_create"),
        json={"name": name, "metadata": {"scope": "local"}},
    )
    assert created.status_code == 201
    item = created.json()["item"]
    resource_id = item["id"]
    assert item["tenant_id"] == 1
    assert item["project_id"] == 1
    assert item["environment"] == "local"

    same_scope = client.get(
        "/v1/policies",
        headers=scoped_admin_headers("req_scoped_same"),
    )
    other_tenant = client.get(
        "/v1/policies",
        headers=scoped_admin_headers("req_scoped_tenant", tenant_id=2),
    )
    other_project = client.get(
        "/v1/policies",
        headers=scoped_admin_headers("req_scoped_project", project_id=2),
    )
    other_environment = client.get(
        "/v1/policies",
        headers=scoped_admin_headers("req_scoped_environment", environment="prod"),
    )

    assert any(record["id"] == resource_id for record in same_scope.json()["items"])
    assert all(record["id"] != resource_id for record in other_tenant.json()["items"])
    assert all(record["id"] != resource_id for record in other_project.json()["items"])
    assert all(record["id"] != resource_id for record in other_environment.json()["items"])

    blocked_update = client.patch(
        f"/v1/policies/{resource_id}",
        headers=scoped_admin_headers("req_scoped_update", environment="prod"),
        json={"name": "should-not-update"},
    )
    blocked_delete = client.delete(
        f"/v1/policies/{resource_id}",
        headers=scoped_admin_headers("req_scoped_delete", project_id=2),
    )

    assert blocked_update.status_code == 404
    assert blocked_delete.status_code == 404


def test_policies_admin_collection_persists_to_database(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database_url = f"sqlite:///{tmp_path / 'admin.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    client = TestClient(create_app())
    policy_name = f"persisted-policy-{uuid4().hex[:8]}"

    created = client.post(
        "/v1/policies",
        headers=scoped_admin_headers("req_policy_persist"),
        json={"name": policy_name, "metadata": {"source": "admin-api"}},
    )

    assert created.status_code == 201
    session = create_session_factory(database_url)()
    try:
        record = session.get(Policy, created.json()["item"]["id"])
        assert record is not None
        assert record.tenant_id == 1
        assert record.project_id == 1
        assert record.metadata_json["name"] == policy_name
        assert record.metadata_json["source"] == "admin-api"
    finally:
        session.close()


def test_admin_artifact_reads_are_isolated_by_request_scope() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/v1/artifacts",
        headers=scoped_admin_headers("req_artifact_create"),
        json={"name": f"artifact-{uuid4().hex[:8]}"},
    )
    assert created.status_code == 201
    artifact_id = created.json()["item"]["id"]

    visible = client.get(
        f"/v1/artifacts/{artifact_id}",
        headers=scoped_admin_headers("req_artifact_visible"),
    )
    hidden = client.get(
        f"/v1/artifacts/{artifact_id}",
        headers=scoped_admin_headers("req_artifact_hidden", environment="prod"),
    )

    assert visible.status_code == 200
    assert hidden.status_code == 404
    assert hidden.json()["error_code"] == "resource_not_found"


def test_incident_decision_actions_update_persisted_admin_record() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/v1/incidents",
        headers=scoped_admin_headers("req_incident_create"),
        json={"name": f"incident-{uuid4().hex[:8]}"},
    )
    assert created.status_code == 201
    incident_id = created.json()["item"]["id"]

    acknowledged = client.post(
        f"/v1/incidents/{incident_id}/acknowledge",
        headers=scoped_admin_headers("req_incident_ack"),
        json={
            "audit_note": "triaged in console",
            "decision_payload": {"acknowledged_by": "console"},
        },
    )
    listed = client.get("/v1/incidents", headers=scoped_admin_headers("req_incident_list"))

    assert acknowledged.status_code == 200
    assert acknowledged.json()["item"]["status"] == "acknowledged"
    persisted = next(item for item in listed.json()["items"] if item["id"] == incident_id)
    assert persisted["status"] == "acknowledged"
    assert persisted["metadata"]["decision_payload"] == {"acknowledged_by": "console"}


def test_human_task_decision_actions_update_persisted_admin_record(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database_url = f"sqlite:///{tmp_path / 'admin-human-tasks.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    client = TestClient(create_app())

    created = client.post(
        "/v1/human-tasks/1/approve",
        headers=scoped_admin_headers("req_human_task_approve"),
        json={"decision_payload": {"approved": True}},
    )
    listed = client.get("/v1/human-tasks", headers=scoped_admin_headers("req_human_task_list"))

    assert created.status_code == 200
    assert created.json()["item"]["status"] == "approved"
    assert created.json()["audit_required"] is True
    assert any(item["id"] == 1 for item in listed.json()["items"])
    session = create_session_factory(database_url)()
    try:
        record = session.get(HumanTask, 1)
        assert record is not None
        assert record.status == "approved"
        assert record.decision_ref == "inline:decision"
    finally:
        session.close()


def test_admin_policy_simulate_returns_matching_scope_and_audit_preview() -> None:
    client = TestClient(create_app())

    created = client.post(
        "/v1/policies",
        headers=scoped_admin_headers("req_policy_simulate_seed"),
        json={
            "name": "deny-tool-write",
            "resource_type": "tool",
            "action": "call",
            "decision": "deny",
            "reason": "tool_write_denied",
        },
    )
    simulated = client.post(
        "/v1/policies/simulate",
        headers=scoped_admin_headers("req_policy_simulate"),
        json={
            "draft_policy": {
                "name": "approve-tool-write",
                "resource_type": "tool",
                "action": "call",
                "decision": "require_approval",
                "priority": 100,
                "reason": "tool_write_requires_review",
            },
            "sample": {
                "resource_type": "tool",
                "resource_id": 11,
                "action": "call",
                "environment": "local",
            },
        },
    )

    assert created.status_code == 201
    assert simulated.status_code == 200
    body = simulated.json()
    assert body["decision"]["result"] == "require_approval"
    assert body["matched_resources"] == [
        {
            "resource_type": "tool",
            "resource_id": 11,
            "action": "call",
            "environment": "local",
        }
    ]
    assert body["audit_preview"]["action"] == "policy.simulate"
    assert body["conflict_warnings"][0]["code"] == "priority_conflict"


def test_admin_human_task_decision_response_includes_resume_outcome_context(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-human-task-resume.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    admin_router_module = importlib.import_module("dimoo_run.api.admin.router")
    admin_router_module._HUMAN_TASK_CONTEXT.clear()
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session = create_session_factory(database_url)()
    try:
        task = HumanTask(
            id=42,
            tenant_id=1,
            project_id=1,
            type="approval",
            status="pending",
            payload_ref="inline:payload",
        )
        session.add(task)
        session.commit()
    finally:
        session.close()
    client = TestClient(create_app())

    response = client.post(
        "/v1/human-tasks/42/reject",
        headers=scoped_admin_headers("req_human_task_resume"),
        json={
            "decision_payload": {
                "comment": "Need security review before resuming.",
                "decided_by": "operator-7",
            }
        },
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["status"] == "rejected"
    assert item["resume_outcome"] == {
        "status": "blocked",
        "task_id": 42,
        "decision": "rejected",
    }


def test_platform_setting_collections_persist_to_database(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database_url = f"sqlite:///{tmp_path / 'admin-platform-settings.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    client = TestClient(create_app())

    exporter = client.post(
        "/v1/observability/exporters",
        headers=scoped_admin_headers("req_exporter_create"),
        json={"name": "otel-dev", "exporter_type": "otlp", "target_ref": "http://otel:4318"},
    )
    sandbox = client.post(
        "/v1/sandbox/policies",
        headers=scoped_admin_headers("req_sandbox_create"),
        json={"name": "locked-down", "network_policy": "deny_all"},
    )

    assert exporter.status_code == 201
    assert sandbox.status_code == 201
    session = create_session_factory(database_url)()
    try:
        exporter_record = session.get(ObservabilityExporter, exporter.json()["item"]["id"])
        sandbox_record = session.get(SandboxPolicy, sandbox.json()["item"]["id"])
        assert exporter_record is not None
        assert exporter_record.name == "otel-dev"
        assert exporter_record.exporter_type == "otlp"
        assert sandbox_record is not None
        assert sandbox_record.name == "locked-down"
        assert sandbox_record.network_policy == "deny_all"
    finally:
        session.close()


def test_strong_parent_admin_collection_rejects_missing_parent_field() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/alerts/rules",
        headers=scoped_admin_headers("req_alert_missing_parent"),
        json={"name": f"alert-{uuid4().hex[:8]}"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_admin_resource"
    assert response.json()["details"]["missing_fields"] == ["channel_id"]


def test_alert_rule_admin_collection_persists_with_parent_channel(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database_url = f"sqlite:///{tmp_path / 'admin-alerts.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    client = TestClient(create_app())

    channel = client.post(
        "/v1/notifications/channels",
        headers=scoped_admin_headers("req_channel_create"),
        json={"name": "ops-webhook", "type": "webhook", "target_ref": "https://hooks.example.test"},
    )
    assert channel.status_code == 201

    alert = client.post(
        "/v1/alerts/rules",
        headers=scoped_admin_headers("req_alert_create"),
        json={
            "name": "error-rate",
            "channel_id": channel.json()["item"]["id"],
            "signal": "runtime.error_rate",
            "threshold": "2.5",
        },
    )

    assert alert.status_code == 201
    session = create_session_factory(database_url)()
    try:
        record = session.get(AlertRule, alert.json()["item"]["id"])
        assert record is not None
        assert record.channel_id == channel.json()["item"]["id"]
        assert record.threshold == 2.5
    finally:
        session.close()


def test_published_surface_and_ingress_route_persist_with_parent_resources(  # type: ignore[no-untyped-def]
    tmp_path,
    monkeypatch,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-surfaces.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    client = TestClient(create_app())
    client.get("/v1/identity/tenants", headers=scoped_admin_headers("req_seed_scope"))

    session = create_session_factory(database_url)()
    try:
        agent = Agent(
            tenant_id=1,
            project_id=1,
            name=f"surface-agent-{uuid4().hex[:8]}",
            status="active",
        )
        session.add(agent)
        session.flush()
        version = AgentVersion(
            agent_id=agent.id,
            version="1.0.0",
            package_uri="file://agent",
            framework="langgraph",
            adapter="python",
            entrypoint="agent:app",
            capabilities_json={},
            manifest_json={},
            status="ready",
        )
        session.add(version)
        session.flush()
        deployment = Deployment(
            tenant_id=1,
            project_id=1,
            agent_id=agent.id,
            agent_version_id=version.id,
            environment="local",
            desired_status="running",
            runtime_status="running",
            replicas=1,
            config_json={},
        )
        session.add(deployment)
        session.commit()
        deployment_id = deployment.id
    finally:
        session.close()

    surface = client.post(
        "/v1/published-surfaces",
        headers=scoped_admin_headers("req_surface_create"),
        json={"name": "public-support", "deployment_id": deployment_id, "type": "http"},
    )
    assert surface.status_code == 201

    route = client.post(
        "/v1/ingress-routes",
        headers=scoped_admin_headers("req_route_create"),
        json={
            "name": "support-route",
            "surface_id": surface.json()["item"]["id"],
            "path": "/support",
            "auth_mode": "api_key",
        },
    )
    assert route.status_code == 201

    session = create_session_factory(database_url)()
    try:
        persisted_surface = session.get(PublishedSurface, surface.json()["item"]["id"])
        persisted_route = session.get(IngressRoute, route.json()["item"]["id"])
        assert persisted_surface is not None
        assert persisted_surface.deployment_id == deployment_id
        assert persisted_route is not None
        assert persisted_route.surface_id == persisted_surface.id
        assert persisted_route.path == "/support"
    finally:
        session.close()


def test_scope_management_collections_are_seeded() -> None:
    client = TestClient(create_app())

    tenants = client.get("/v1/identity/tenants", headers=admin_headers("req_tenants"))
    projects = client.get("/v1/identity/projects", headers=admin_headers("req_projects"))
    environments = client.get(
        "/v1/identity/environments",
        headers=admin_headers("req_environments"),
    )

    assert tenants.status_code == 200
    assert projects.status_code == 200
    assert environments.status_code == 200
    assert any(item["id"] == 1 for item in tenants.json()["items"])
    assert any(item["id"] == 1 for item in projects.json()["items"])
    assert any(item["environment"] == "local" for item in environments.json()["items"])


def test_console_admin_surface_collections_support_create_and_list() -> None:
    client = TestClient(create_app())
    name = f"console-created-{uuid4().hex[:8]}"
    paths = [
        "/v1/identity/users",
        "/v1/identity/tenants",
        "/v1/identity/projects",
        "/v1/identity/environments",
        "/v1/identity/roles",
        "/v1/secrets",
        "/v1/model-gateways",
        "/v1/webhooks/subscriptions",
        "/v1/backups/restore-jobs",
        "/v1/incidents",
    ]

    for path in paths:
        created = client.post(path, headers=admin_headers(), json={"name": name})
        listed = client.get(path, headers=admin_headers())

        assert created.status_code == 201, path
        assert listed.status_code == 200, path
        assert any(item["name"] == name for item in listed.json()["items"]), path


def test_machine_identity_service_account_api_key_lifecycle() -> None:
    client = TestClient(create_app())

    service_account = client.post(
        "/v1/identity/service-accounts",
        headers=admin_headers("req_sa_create"),
        json={
            "name": "ci-deployer",
            "description": "CI deployment identity",
            "tenant_id": 1,
            "project_id": 1,
            "permissions": ["agent:read", "agent:deploy"],
        },
    )
    assert service_account.status_code == 201
    service_account_id = service_account.json()["item"]["id"]

    denied_key = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=admin_headers("req_key_denied"),
        json={"name": "too-powerful", "scopes": ["agent:read", "secret:read"]},
    )
    assert denied_key.status_code == 403
    assert denied_key.json()["error_code"] == "api_key_scope_exceeds_owner"

    created_key = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=admin_headers("req_key_create"),
        json={"name": "deploy-key", "scopes": ["agent:read"]},
    )
    assert created_key.status_code == 201
    payload = created_key.json()
    assert payload["plain_key"].startswith("dr_")
    key_id = payload["item"]["id"]

    listed_keys = client.get(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=admin_headers("req_key_list"),
    )
    assert listed_keys.status_code == 200
    assert "plain_key" not in listed_keys.json()["items"][0]
    assert listed_keys.json()["items"][0]["scopes"] == ["agent:read"]

    allowed = client.get(
        "/v1/agents",
        headers={
            "Authorization": f"Bearer {payload['plain_key']}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
            "X-Request-Id": "req_key_allowed",
        },
    )
    assert allowed.status_code == 200

    disabled = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys/{key_id}/disable",
        headers=admin_headers("req_key_disable"),
    )
    assert disabled.status_code == 200
    assert disabled.json()["item"]["status"] == "disabled"

    rejected = client.get(
        "/v1/agents",
        headers={
            "Authorization": f"Bearer {payload['plain_key']}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
            "X-Request-Id": "req_key_rejected",
        },
    )
    assert rejected.status_code == 401

    enabled = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys/{key_id}/enable",
        headers=admin_headers("req_key_enable"),
    )
    assert enabled.status_code == 200
    assert enabled.json()["item"]["status"] == "active"

    allowed_again = client.get(
        "/v1/agents",
        headers={
            "Authorization": f"Bearer {payload['plain_key']}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
            "X-Request-Id": "req_key_allowed_again",
        },
    )
    assert allowed_again.status_code == 200

    deleted = client.delete(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys/{key_id}",
        headers=admin_headers("req_key_delete"),
    )
    assert deleted.status_code == 200
    assert deleted.json()["item"]["status"] == "deleted"

    listed_after_delete = client.get(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=admin_headers("req_key_list_after_delete"),
    )
    assert all(item["id"] != key_id for item in listed_after_delete.json()["items"])

    audit_logs = client.get("/v1/audit-logs", headers=admin_headers("req_audit_logs"))
    actions = [item.get("action") for item in audit_logs.json()["items"]]
    assert "identity.service_account.create" in actions
    assert "identity.api_key.create" in actions
    assert "identity.api_key.disable" in actions
    assert "identity.api_key.enable" in actions
    assert "identity.api_key.delete" in actions


def test_top_level_api_keys_lists_accessible_machine_keys_without_plain_secret() -> None:
    client = TestClient(create_app())

    service_account = client.post(
        "/v1/identity/service-accounts",
        headers=admin_headers("req_sa_for_keys"),
        json={
            "name": "api-key-index-sa",
            "tenant_id": 1,
            "project_id": 1,
            "permissions": ["agent:read"],
        },
    )
    assert service_account.status_code == 201
    service_account_id = service_account.json()["item"]["id"]
    created_key = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=admin_headers("req_top_level_key_create"),
        json={"name": "indexed-key", "scopes": ["agent:read"]},
    )
    assert created_key.status_code == 201

    response = client.get("/v1/api-keys", headers=admin_headers("req_top_level_key_list"))

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["name"] == "indexed-key"
    assert body["items"][0]["owner_id"] == service_account_id
    assert "plain_key" not in body["items"][0]


def test_machine_identity_service_account_update_and_delete() -> None:
    client = TestClient(create_app())

    service_account = client.post(
        "/v1/identity/service-accounts",
        headers=admin_headers("req_sa_update_create"),
        json={
            "name": "editable-sa",
            "tenant_id": 1,
            "project_id": 1,
            "permissions": ["agent:read", "run:read"],
        },
    )
    assert service_account.status_code == 201
    service_account_id = service_account.json()["item"]["id"]

    updated = client.patch(
        f"/v1/identity/service-accounts/{service_account_id}",
        headers=admin_headers("req_sa_update"),
        json={"name": "edited-sa", "permissions": ["agent:read"], "status": "active"},
    )
    assert updated.status_code == 200
    assert updated.json()["item"]["name"] == "edited-sa"
    assert updated.json()["item"]["permissions"] == ["agent:read"]

    deleted = client.delete(
        f"/v1/identity/service-accounts/{service_account_id}",
        headers=admin_headers("req_sa_delete"),
    )
    listed = client.get("/v1/identity/service-accounts", headers=admin_headers("req_sa_list"))

    assert deleted.status_code == 200
    assert deleted.json()["item"]["status"] == "deleted"
    assert all(item["id"] != service_account_id for item in listed.json()["items"])


def test_service_account_permission_reduction_disables_excessive_api_keys() -> None:
    client = TestClient(create_app())

    service_account = client.post(
        "/v1/identity/service-accounts",
        headers=admin_headers("req_sa_reduce_create"),
        json={
            "name": "reduced-sa",
            "tenant_id": 1,
            "project_id": 1,
            "permissions": ["agent:read", "run:read"],
        },
    )
    service_account_id = service_account.json()["item"]["id"]
    key = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=admin_headers("req_sa_reduce_key"),
        json={"name": "run-key", "scopes": ["run:read"]},
    )
    assert key.status_code == 201
    key_id = key.json()["item"]["id"]

    updated = client.patch(
        f"/v1/identity/service-accounts/{service_account_id}",
        headers=admin_headers("req_sa_reduce"),
        json={"permissions": ["agent:read"]},
    )
    listed_keys = client.get(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=admin_headers("req_sa_reduce_keys"),
    )

    assert updated.status_code == 200
    assert listed_keys.json()["items"][0]["status"] == "disabled"

    enable_denied = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys/{key_id}/enable",
        headers=admin_headers("req_sa_reduce_key_enable_denied"),
    )
    assert enable_denied.status_code == 403


def test_machine_identity_rejects_payload_scope_outside_actor_scope() -> None:
    client = TestClient(create_app())
    authenticator = default_api_key_authenticator()
    permissions = {"admin:read", "identity:service-account:write"}
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="limited-admin",
        permissions=permissions,
        created_by="test",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="limited-admin-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=permissions,
        created_by="test",
    )
    headers = {
        **admin_headers("req_scope_denied"),
        "Authorization": f"Bearer {plain_key}",
    }

    response = client.post(
        "/v1/identity/service-accounts",
        headers=headers,
        json={
            "name": "cross-scope",
            "tenant_id": 2,
            "project_id": 1,
            "permissions": ["agent:read"],
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "scope_not_allowed"


def test_admin_artifact_read_returns_stable_not_found_response() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/v1/artifacts/999999",
        headers=admin_headers("req_artifact_read"),
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "resource_not_found"
    assert response.json()["request_id"] == "req_artifact_read"
