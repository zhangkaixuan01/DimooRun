import os
import tempfile
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from dimoo_run.api.dependencies import (
    default_api_key_authenticator,
    reset_api_key_authenticator,
)
from dimoo_run.api.native.deployments import (
    default_deployment_control,
    reset_deployment_control,
)
from dimoo_run.api.native.runtime import (
    NativeRuntimeStore,
    default_native_runtime,
    reset_native_runtime,
)
from dimoo_run.domain.enums import RunStatus, TaskStatus
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.packages.validation import validation_token
from dimoo_run.runtime.capacity import (
    WorkerRegistry,
    default_worker_registry,
    reset_worker_registry,
)
from dimoo_run.server import create_app
from fastapi.testclient import TestClient

CONSOLE_RUNTIME_PATHS = [
    "/v1/console/workers",
    "/v1/console/workers/{worker_id}",
    "/v1/console/workers/{worker_id}/{action}",
    "/v1/console/agent-instances",
    "/v1/console/agent-instances/{instance_id}",
    "/v1/console/capacity",
]


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DIMOORUN_NATIVE_RUNTIME_STORE"] = "memory"
    os.environ["DATABASE_URL"] = (
        f"sqlite:///{tempfile.gettempdir()}/dimoorun-console-capacity-{uuid4().hex}.db"
    )
    reset_api_key_authenticator()
    reset_deployment_control()
    reset_native_runtime()
    reset_worker_registry()


def create_api_key(*, scopes: set[str] | None = None) -> tuple[str, ServiceAccountRecord]:
    requested_scopes = scopes or {"agent:read", "agent:write", "agent:deploy", "agent:invoke"}
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="console-runtime",
        permissions=requested_scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="console-runtime-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=requested_scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def auth_headers(
    api_key: str,
    *,
    tenant_id: int = 1,
    project_id: int = 1,
    environment: str = "production",
    audit_reason: str | None = None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": "req_console_capacity",
        "X-Tenant-Id": str(tenant_id),
        "X-Project-Id": str(project_id),
        "X-Environment": environment,
    }
    if audit_reason is not None:
        headers["X-Audit-Reason"] = audit_reason
    return headers


def create_agent_with_version(client: TestClient, key: str) -> tuple[int, int]:
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(key),
        json={"name": "support-agent"},
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]
    version = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(key),
        json={
            "version": "1.0.0",
            "package_uri": "file://support-agent",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": {
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": "agent:create_agent",
                },
                "capabilities": {"invoke": True},
                "validation_token": validation_token(
                    package_uri="file://support-agent",
                    framework="langgraph",
                    adapter="langgraph",
                    entrypoint="agent:create_agent",
                    manifest={
                        "runtime": {
                            "framework": "langgraph",
                            "adapter": "langgraph",
                            "entrypoint": "agent:create_agent",
                        },
                        "capabilities": {"invoke": True},
                    },
                ),
            },
            "status": "ready",
        },
    )
    assert version.status_code == 201
    return agent_id, version.json()["id"]


def create_deployment(client: TestClient, key: str, *, environment: str = "production") -> int:
    agent_id, version_id = create_agent_with_version(client, key)
    response = client.post(
        "/v1/deployments",
        headers=auth_headers(key, environment=environment),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": environment,
            "desired_status": "active",
            "replicas": 2,
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def create_task(
    client: TestClient,
    key: str,
    deployment_id: int,
    *,
    message: str,
) -> tuple[int, int]:
    response = client.post(
        f"/v1/deployments/{deployment_id}/tasks",
        headers=auth_headers(key),
        json={"input": {"message": message}},
    )
    assert response.status_code == 202
    return response.json()["run_id"], response.json()["task_id"]


def test_runtime_console_paths_are_registered_in_openapi() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in CONSOLE_RUNTIME_PATHS:
        assert path in paths


def test_worker_health_and_control_workflow_blocks_critical_drain_then_succeeds() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    deployment_id = create_deployment(client, key)
    run_id, task_id = create_task(client, key, deployment_id, message="critical task")

    service = default_deployment_control()
    deployment = service.deployments.get(deployment_id)
    instance = service.instances.register_loading(
        tenant_id=deployment.tenant_id,
        project_id=deployment.project_id,
        deployment_id=deployment.id,
        agent_id=deployment.agent_id,
        agent_version_id=deployment.agent_version_id,
        worker_id="worker_1",
        execution_profile_id="default",
    )
    service.instances.mark_ready(instance.id)
    instance.running_runs = 1
    instance.metadata["concurrency_limit"] = 4

    runtime = default_native_runtime()
    assert isinstance(runtime, NativeRuntimeStore)
    task = runtime.tasks[task_id]
    task.status = TaskStatus.running
    task.worker_id = "worker_1"
    task.quota_blocking_reason = {"severity": "critical"}
    run = runtime.runs[run_id]
    run.status = RunStatus.running

    registry = default_worker_registry()
    registry.heartbeat(
        worker_id="worker_1",
        tenant_id=1,
        project_id=1,
        environment="production",
        status="running",
        queues=["default", "priority"],
        version="2026.06.10",
        capacity=2,
        now=datetime.now(UTC) - timedelta(seconds=12),
    )

    workers = client.get("/v1/console/workers", headers=auth_headers(key))
    assert workers.status_code == 200
    item = workers.json()["items"][0]
    assert item["worker_id"] == "worker_1"
    assert item["capacity"] == 2
    assert item["active_attempts"] == 1
    assert item["queues"] == ["default", "priority"]
    assert item["readiness"] == "ready"

    detail = client.get("/v1/console/workers/worker_1", headers=auth_headers(key))
    assert detail.status_code == 200
    actions = {entry["action"]: entry for entry in detail.json()["item"]["actions"]}
    assert actions["drain"]["available"] is False
    assert "active critical attempt" in actions["drain"]["disabled_reasons"][0]

    blocked = client.post(
        "/v1/console/workers/worker_1/drain",
        headers=auth_headers(key, audit_reason="drain worker"),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error_code"] == "worker_action_blocked"

    task.quota_blocking_reason = None
    drained = client.post(
        "/v1/console/workers/worker_1/drain",
        headers=auth_headers(key, audit_reason="drain worker"),
    )
    assert drained.status_code == 200
    assert drained.json()["item"]["drain_status"] == "draining"

    resumed = client.post(
        "/v1/console/workers/worker_1/undrain",
        headers=auth_headers(key, audit_reason="resume scheduling"),
    )
    assert resumed.status_code == 200
    assert resumed.json()["item"]["drain_status"] == "active"

    task.status = TaskStatus.succeeded
    quarantined = client.post(
        "/v1/console/workers/worker_1/quarantine",
        headers=auth_headers(key, audit_reason="quarantine worker"),
    )
    assert quarantined.status_code == 200
    assert quarantined.json()["item"]["drain_status"] == "quarantined"

    restarted = client.post(
        "/v1/console/workers/worker_1/restart-request",
        headers=auth_headers(key, audit_reason="restart worker"),
    )
    assert restarted.status_code == 200
    assert restarted.json()["item"]["restart_requested_at"] is not None


def test_agent_instances_and_capacity_summary_surface_runtime_pressure() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    deployment_id = create_deployment(client, key)
    run_id_1, task_id_1 = create_task(client, key, deployment_id, message="queued")
    run_id_2, task_id_2 = create_task(client, key, deployment_id, message="failed")

    service = default_deployment_control()
    deployment = service.deployments.get(deployment_id)
    instance = service.instances.register_loading(
        tenant_id=deployment.tenant_id,
        project_id=deployment.project_id,
        deployment_id=deployment.id,
        agent_id=deployment.agent_id,
        agent_version_id=deployment.agent_version_id,
        worker_id="worker_2",
        execution_profile_id="high-memory",
    )
    service.instances.mark_ready(instance.id)
    instance.running_runs = 2
    instance.error = "provider timeout"
    instance.metadata["recent_failures"] = 3
    instance.metadata["concurrency_limit"] = 8

    runtime = default_native_runtime()
    assert isinstance(runtime, NativeRuntimeStore)
    task_1 = runtime.tasks[task_id_1]
    task_1.status = TaskStatus.queued
    task_2 = runtime.tasks[task_id_2]
    task_2.status = TaskStatus.dead_letter
    task_2.worker_id = "worker_2"
    task_2.error = {"message": "provider timeout"}
    task_2.dead_letter_reason = "provider timeout"
    run_1 = runtime.runs[run_id_1]
    run_1.status = RunStatus.pending
    run_2 = runtime.runs[run_id_2]
    run_2.status = RunStatus.failed
    run_2.error = {"message": "provider timeout"}

    registry = default_worker_registry()
    registry.heartbeat(
        worker_id="worker_2",
        tenant_id=1,
        project_id=1,
        environment="production",
        status="running",
        queues=["default"],
        version="2026.06.10",
        capacity=1,
        now=datetime.now(UTC) - timedelta(seconds=20),
    )

    instances = client.get("/v1/console/agent-instances", headers=auth_headers(key))
    assert instances.status_code == 200
    instance_item = instances.json()["items"][0]
    assert instance_item["worker_id"] == "worker_2"
    assert instance_item["recent_failures"] == 3
    assert instance_item["concurrency_limit"] == 8
    assert len(instance_item["runtime_config_hash"]) == 12

    instance_detail = client.get(
        f"/v1/console/agent-instances/{instance.id}",
        headers=auth_headers(key),
    )
    assert instance_detail.status_code == 200
    assert instance_detail.json()["item"]["deployment_runtime_status"] == "not_loaded"

    capacity = client.get("/v1/console/capacity", headers=auth_headers(key))
    assert capacity.status_code == 200
    summary = capacity.json()["item"]
    assert summary["queue_backlog"] == 1
    assert summary["dead_letter_pressure"] == 1
    assert summary["recommended_action"] == "investigate_dead_letters"
    assert summary["queues"][0]["queue"] == "default"
    assert summary["queues"][0]["dead_letter"] == 1


def test_worker_snapshots_persist_across_registry_instances_and_scope_capacity() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, version_id = create_agent_with_version(client, key)
    production_deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key, environment="production"),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "production",
            "desired_status": "active",
            "replicas": 2,
        },
    )
    assert production_deployment.status_code == 201
    production_deployment_id = production_deployment.json()["id"]
    staging_deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key, environment="staging"),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "staging",
            "desired_status": "active",
            "replicas": 1,
        },
    )
    assert staging_deployment.status_code == 201
    staging_deployment_id = staging_deployment.json()["id"]
    prod_run_id, prod_task_id = create_task(
        client,
        key,
        production_deployment_id,
        message="prod queued",
    )
    staging_run_id, staging_task_id = create_task(
        client,
        key,
        staging_deployment_id,
        message="staging running",
    )

    runtime = default_native_runtime()
    assert isinstance(runtime, NativeRuntimeStore)
    runtime.tasks[prod_task_id].status = TaskStatus.queued
    runtime.tasks[staging_task_id].status = TaskStatus.running
    runtime.tasks[staging_task_id].worker_id = "worker_staging"
    runtime.runs[prod_run_id].status = RunStatus.pending
    runtime.runs[staging_run_id].status = RunStatus.running

    writer = WorkerRegistry(database_url=os.environ["DATABASE_URL"])
    writer.heartbeat(
        worker_id="worker_prod",
        tenant_id=1,
        project_id=1,
        environment="production",
        status="running",
        queues=["default"],
        version="2026.06.10",
        capacity=2,
        now=datetime.now(UTC) - timedelta(seconds=5),
    )
    writer.heartbeat(
        worker_id="worker_staging",
        tenant_id=1,
        project_id=1,
        environment="staging",
        status="running",
        queues=["default"],
        version="2026.06.10",
        capacity=1,
        now=datetime.now(UTC) - timedelta(seconds=7),
    )

    reader = WorkerRegistry(database_url=os.environ["DATABASE_URL"])
    persisted = reader.get(
        "worker_prod",
        tenant_id=1,
        project_id=1,
        environment="production",
    )
    assert persisted is not None
    assert persisted.worker_id == "worker_prod"

    production_workers = client.get("/v1/console/workers", headers=auth_headers(key))
    assert production_workers.status_code == 200
    assert [item["worker_id"] for item in production_workers.json()["items"]] == ["worker_prod"]

    capacity = client.get("/v1/console/capacity", headers=auth_headers(key))
    assert capacity.status_code == 200
    summary = capacity.json()["item"]
    assert summary["queue_backlog"] == 1
    assert summary["active_attempts"] == 0
    assert summary["total_capacity"] == 2


def test_worker_controls_only_mutate_requested_scope_when_worker_ids_are_reused() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    writer = WorkerRegistry(database_url=os.environ["DATABASE_URL"])
    now = datetime.now(UTC)
    writer.heartbeat(
        worker_id="worker_shared",
        tenant_id=1,
        project_id=1,
        environment="production",
        status="running",
        queues=["default"],
        version="2026.06.10",
        capacity=2,
        now=now - timedelta(seconds=5),
    )
    writer.heartbeat(
        worker_id="worker_shared",
        tenant_id=1,
        project_id=1,
        environment="staging",
        status="running",
        queues=["default"],
        version="2026.06.10",
        capacity=1,
        now=now - timedelta(seconds=7),
    )

    response = client.post(
        "/v1/console/workers/worker_shared/drain",
        headers=auth_headers(key, environment="production", audit_reason="drain prod worker"),
    )
    assert response.status_code == 200
    assert response.json()["item"]["drain_status"] == "draining"

    reader = WorkerRegistry(database_url=os.environ["DATABASE_URL"])
    production = reader.get(
        "worker_shared",
        tenant_id=1,
        project_id=1,
        environment="production",
    )
    staging = reader.get(
        "worker_shared",
        tenant_id=1,
        project_id=1,
        environment="staging",
    )
    assert production is not None
    assert staging is not None
    assert production.drain_status == "draining"
    assert staging.drain_status == "active"


def test_worker_detail_and_capacity_ignore_other_environment_tasks_when_worker_ids_are_reused(
) -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    agent_id, version_id = create_agent_with_version(client, key)
    production_deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key, environment="production"),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "production",
            "desired_status": "active",
            "replicas": 2,
        },
    )
    assert production_deployment.status_code == 201
    staging_deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(key, environment="staging"),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "staging",
            "desired_status": "active",
            "replicas": 1,
        },
    )
    assert staging_deployment.status_code == 201
    prod_run_id, prod_task_id = create_task(
        client,
        key,
        production_deployment.json()["id"],
        message="prod queued",
    )
    staging_run_id, staging_task_id = create_task(
        client,
        key,
        staging_deployment.json()["id"],
        message="staging running",
    )

    runtime = default_native_runtime()
    assert isinstance(runtime, NativeRuntimeStore)
    runtime.tasks[prod_task_id].status = TaskStatus.queued
    runtime.tasks[prod_task_id].worker_id = "worker_shared"
    runtime.tasks[staging_task_id].status = TaskStatus.running
    runtime.tasks[staging_task_id].worker_id = "worker_shared"
    runtime.runs[prod_run_id].status = RunStatus.pending
    runtime.runs[staging_run_id].status = RunStatus.running

    writer = WorkerRegistry(database_url=os.environ["DATABASE_URL"])
    now = datetime.now(UTC)
    writer.heartbeat(
        worker_id="worker_shared",
        tenant_id=1,
        project_id=1,
        environment="production",
        status="running",
        queues=["default"],
        version="2026.06.10",
        capacity=2,
        now=now - timedelta(seconds=5),
    )
    writer.heartbeat(
        worker_id="worker_shared",
        tenant_id=1,
        project_id=1,
        environment="staging",
        status="running",
        queues=["default"],
        version="2026.06.10",
        capacity=1,
        now=now - timedelta(seconds=7),
    )

    detail = client.get(
        "/v1/console/workers/worker_shared",
        headers=auth_headers(key, environment="production"),
    )
    assert detail.status_code == 200
    assert detail.json()["item"]["active_attempts"] == 0
    assert detail.json()["item"]["active_task_ids"] == []
    assert detail.json()["item"]["active_run_ids"] == []

    production_headers = auth_headers(key, environment="production")
    capacity = client.get("/v1/console/capacity", headers=production_headers)
    assert capacity.status_code == 200
    summary = capacity.json()["item"]
    assert summary["queue_backlog"] == 1
    assert summary["active_attempts"] == 0
    assert summary["total_capacity"] == 2
