import os
import tempfile
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from dimoo_run.api.dependencies import reset_api_key_authenticator
from dimoo_run.api.native.deployments import reset_deployment_control
from dimoo_run.api.native.runtime import (
    NativeRuntimeStore,
    default_native_runtime,
    reset_native_runtime,
)
from dimoo_run.core.events import AgentEvent
from dimoo_run.domain.enums import RunStatus, TaskStatus
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.packages.validation import validation_token
from dimoo_run.runtime.capacity import default_worker_registry, reset_worker_registry
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = (
        f"sqlite:///{tempfile.gettempdir()}/dimoorun-metrics-{uuid4().hex}.db"
    )
    reset_api_key_authenticator()
    reset_deployment_control()
    reset_native_runtime()
    reset_worker_registry()


def create_api_key() -> tuple[str, ServiceAccountRecord]:
    from dimoo_run.api.dependencies import default_api_key_authenticator

    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="metrics-api",
        permissions={"agent:read", "agent:write", "agent:deploy", "agent:invoke"},
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="metrics-api-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes={"agent:read", "agent:write", "agent:deploy", "agent:invoke"},
        created_by="admin_1",
    )
    return plain_key, service_account


def headers(api_key: str, request_id: str = "req_metrics") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": request_id,
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "production",
    }


def create_agent_with_version(client: TestClient, api_key: str) -> tuple[int, int]:
    agent = client.post(
        "/v1/agents",
        headers=headers(api_key),
        json={"name": "support-agent"},
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]
    version = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=headers(api_key),
        json={
            "version": "0.1.0",
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


def create_deployment(client: TestClient, api_key: str) -> int:
    agent_id, version_id = create_agent_with_version(client, api_key)
    deployment = client.post(
        "/v1/deployments",
        headers=headers(api_key),
        json={
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "environment": "production",
            "desired_status": "active",
            "replicas": 2,
        },
    )
    assert deployment.status_code == 201
    return int(deployment.json()["id"])


def test_runtime_metrics_summary_and_prometheus_share_semantics() -> None:
    client = TestClient(create_app())
    api_key, _ = create_api_key()
    deployment_id = create_deployment(client, api_key)
    task = client.post(
        f"/v1/deployments/{deployment_id}/tasks",
        headers=headers(api_key, "req_metrics_summary"),
        json={"input": {"message": "hello"}},
    )
    assert task.status_code == 202

    runtime = cast(NativeRuntimeStore, default_native_runtime())
    run = runtime.runs[task.json()["run_id"]]
    run.status = RunStatus.failed
    run.started_at = datetime(2026, 6, 11, 10, 0, tzinfo=UTC)
    run.finished_at = datetime(2026, 6, 11, 10, 0, 2, tzinfo=UTC)
    run.error = {"message": "provider timeout"}
    worker_task = runtime.tasks[task.json()["task_id"]]
    worker_task.status = TaskStatus.dead_letter
    worker_task.dead_letter_reason = "provider timeout"
    worker_task.worker_id = "worker-a"

    registry = default_worker_registry()
    registry.heartbeat(
        worker_id="worker-a",
        tenant_id=1,
        project_id=1,
        environment="production",
        status="running",
        queues=["default"],
        version="phase5",
        capacity=2,
        now=datetime(2026, 6, 11, 10, 0, 1, tzinfo=UTC),
    )

    summary = client.get("/v1/runtime/metrics/summary", headers=headers(api_key))

    assert summary.status_code == 200
    body = summary.json()
    assert body["summary"]["queue_backlog"] == 1
    assert body["summary"]["running_tasks"] == 0
    assert body["summary"]["dead_letters"] == 1
    assert body["summary"]["failed_runs"] == 1
    assert body["summary"]["worker_total"] == 1
    assert body["summary"]["active_incidents"] == 1
    assert body["summary"]["p95_latency_ms"] == 2000
    assert body["queues"][0]["dead_letters"] == 1
    assert body["workers"][0]["worker_id"] == "worker-a"
    assert body["active_incidents"][0]["error_summary"] == "provider timeout"

    prometheus = client.get("/metrics", headers=headers(api_key))

    assert prometheus.status_code == 200
    assert 'dimoorun_dead_letters_total 1' in prometheus.text
    assert 'dimoorun_active_incidents 1' in prometheus.text
    assert 'dimoorun_run_latency_ms{quantile="0.95"} 2000' in prometheus.text


def test_runtime_event_query_filters_and_redacts_internal_payloads() -> None:
    client = TestClient(create_app())
    api_key, _ = create_api_key()
    deployment_id = create_deployment(client, api_key)
    task = client.post(
        f"/v1/deployments/{deployment_id}/tasks",
        headers=headers(api_key, "req_metrics_events"),
        json={"input": {"message": "hello"}},
    )
    assert task.status_code == 202

    runtime = cast(NativeRuntimeStore, default_native_runtime())
    runtime.replay_buffer.append(
        task.json()["run_id"],
        None,
        AgentEvent(
            type="agent.message",
            payload={
                "secret": "hide-me",
                "text": "hello",
                "trace_id": "trace_run_1",
                "request_id": "req_metrics_events",
            },
            visibility_level="internal",
        ),
    )

    filtered = client.get(
        "/v1/runtime/events",
        headers=headers(api_key),
        params={"event_type": "agent.message", "trace_id": "trace_run_1"},
    )

    assert filtered.status_code == 200
    body = filtered.json()
    assert len(body) == 1
    assert body[0]["trace_id"] == "trace_run_1"
    assert body[0]["request_id"] == "req_metrics_events"
    assert body[0]["payload"] == {
        "redacted": True,
        "trace_id": "trace_run_1",
        "request_id": "req_metrics_events",
    }

    full = client.get(
        "/v1/runtime/events",
        headers=headers(api_key),
        params={"event_type": "agent.message", "trace_id": "trace_run_1", "redact": "false"},
    )
    assert full.status_code == 200
    assert full.json()[0]["payload"]["secret"] == "hide-me"
