import os
import tempfile
from uuid import uuid4

from dimoo_run.api.compat.langgraph import default_compat_runtime, reset_compat_runtime
from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.deployments import reset_deployment_control
from dimoo_run.compatibility import reset_golden_runner
from dimoo_run.core.events import AgentEvent
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.server import create_app
from fastapi.testclient import TestClient

CONSOLE_COMPAT_PATHS = [
    "/v1/console/compatibility/langgraph/assistants",
    "/v1/console/compatibility/langgraph/assistants/{assistant_id}",
    "/v1/console/compatibility/langgraph/threads",
    "/v1/console/compatibility/langgraph/threads/{thread_id}",
    "/v1/console/compatibility/langgraph/threads/{thread_id}/runs",
    "/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{run_id}",
    "/v1/console/compatibility/langgraph/threads/{thread_id}/runs/stream-probe",
    "/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{run_id}/stream-status",
    "/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{run_id}/events",
    "/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{run_id}/join",
    "/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{run_id}/cancel",
    "/v1/console/compatibility/migration-report",
]


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = (
        f"sqlite:///{tempfile.gettempdir()}/dimoorun-console-compat-{uuid4().hex}.db"
    )
    reset_api_key_authenticator()
    reset_compat_runtime()
    reset_deployment_control()
    reset_golden_runner()


def create_api_key(*, scopes: set[str] | None = None) -> tuple[str, ServiceAccountRecord]:
    requested_scopes = scopes or {"agent:read", "agent:invoke"}
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="console-compatibility",
        permissions=requested_scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="console-compatibility-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=requested_scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": "req_console_compatibility",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
    }


def test_console_compatibility_paths_are_registered() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in CONSOLE_COMPAT_PATHS:
        assert path in paths


def test_console_compatibility_migration_report_explains_unsupported_features() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key(scopes={"agent:read"})

    response = client.post(
        "/v1/console/compatibility/migration-report",
        headers=auth_headers(key),
        json={
            "framework": "langgraph",
            "adapter": "langgraph",
            "capabilities": ["assistants", "hosted_deployments"],
            "streaming_modes": ["events", "messages"],
            "uses_checkpointing": True,
            "required_secrets": ["secret://openai"],
            "custom_tools": ["pagerduty.lookup"],
        },
    )

    assert response.status_code == 200
    report = response.json()["report"]
    golden = response.json()["golden_record"]
    assert report["overall_status"] == "migration_required"
    assert report["checkpoint_requirements"]["required"] is True
    assert "checkpoint runtime store" in report["required_dimoorun_config"]
    assert "policies.tool_approval" in report["required_dimoorun_config"]
    assert report["unsupported_capabilities"][0]["capability"] == "hosted_deployments"
    assert golden["expected_semantics"]["framework"] == "langgraph"
    assert golden["expected_semantics"]["supports_last_event_id_replay"] is True
    assert golden["divergence_reason"] == "compatibility_not_supported"


def test_console_compatibility_explorer_maps_assistant_thread_run_and_stream_probe() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()

    assistant = client.post(
        "/v1/console/compatibility/langgraph/assistants",
        headers=auth_headers(key),
        json={"name": "support-agent"},
    )
    assert assistant.status_code == 200
    assistant_body = assistant.json()
    assistant_id = assistant_body["compat_response"]["assistant_id"]
    assert assistant_body["native_resources"]["agent_id"] == 1
    assert assistant_body["resource_links"][0]["path"] == "/agents"

    listed = client.get(
        "/v1/console/compatibility/langgraph/assistants",
        headers=auth_headers(key),
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    fetched_assistant = client.get(
        f"/v1/console/compatibility/langgraph/assistants/{assistant_id}",
        headers=auth_headers(key),
    )
    assert fetched_assistant.status_code == 200
    assert fetched_assistant.json()["compat_response"]["assistant_id"] == assistant_id

    thread = client.post(
        "/v1/console/compatibility/langgraph/threads",
        headers=auth_headers(key),
        json={},
    )
    assert thread.status_code == 200
    thread_id = thread.json()["compat_response"]["thread_id"]
    fetched_thread = client.get(
        f"/v1/console/compatibility/langgraph/threads/{thread_id}",
        headers=auth_headers(key),
    )
    assert fetched_thread.status_code == 200
    assert fetched_thread.json()["compat_response"]["thread_id"] == thread_id

    run = client.post(
        f"/v1/console/compatibility/langgraph/threads/{thread_id}/runs",
        headers=auth_headers(key),
        json={"assistant_id": assistant_id, "input": {"message": "hello"}},
    )
    assert run.status_code == 200
    run_body = run.json()
    run_id = run_body["compat_response"]["run_id"]
    assert run_body["native_resources"]["task_id"] == 1
    assert {"label": f"Run #{run_id}", "path": f"/runs/{run_id}"} in run_body["resource_links"]
    assert run_body["golden_record"]["expected_semantics"]["compat_status"] == "queued"
    assert run_body["golden_record"]["expected_semantics"]["native_task_id"] == 1

    status = client.get(
        f"/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{run_id}",
        headers=auth_headers(key),
    )
    assert status.status_code == 200
    assert status.json()["compat_response"]["status"] == "queued"

    stream_probe = client.post(
        f"/v1/console/compatibility/langgraph/threads/{thread_id}/runs/stream-probe",
        headers=auth_headers(key),
        json={"assistant_id": assistant_id, "input": {"message": "hello again"}},
    )
    assert stream_probe.status_code == 200
    stream_probe_body = stream_probe.json()
    assert [item["type"] for item in stream_probe_body["stream_events"]] == [
        "run.created",
        "task.queued",
        "run.started",
    ]
    assert stream_probe_body["golden_record"]["expected_semantics"]["stream_mode"] == "events"
    assert stream_probe_body["golden_record"]["expected_semantics"]["event_types"] == [
        "run.created",
        "task.queued",
        "run.started",
    ]
    streamed_run_id = stream_probe_body["compat_response"]["run_id"]
    stream_status = client.get(
        f"/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{streamed_run_id}/stream-status",
        headers=auth_headers(key),
    )
    assert stream_status.status_code == 200
    assert stream_status.json()["stream_status"]["event_count"] == 3
    assert stream_status.json()["stream_status"]["latest_event_id"] == f"{streamed_run_id}:3"
    assert (
        stream_status.json()["golden_record"]["expected_semantics"][
            "supports_last_event_id_replay"
        ]
        is True
    )
    replay = client.get(
        f"/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{streamed_run_id}/events",
        headers=auth_headers(key),
        params={"last_event_id": f"{streamed_run_id}:1"},
    )
    assert replay.status_code == 200
    replay_body = replay.json()
    assert [item["type"] for item in replay_body["stream_events"]] == [
        "task.queued",
        "run.started",
    ]
    assert replay_body["golden_record"]["expected_semantics"][
        "replayed_event_types"
    ] == ["task.queued", "run.started"]
    runtime = default_compat_runtime()
    runtime.replay_buffer.max_events_per_run = 2
    runtime.replay_buffer.append(
        streamed_run_id,
        None,
        AgentEvent(type="run.heartbeat", payload={"source": "probe"}),
    )
    replay_expired = client.get(
        f"/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{streamed_run_id}/events",
        headers=auth_headers(key),
        params={"last_event_id": f"{streamed_run_id}:1"},
    )
    assert replay_expired.status_code == 409
    assert replay_expired.json()["error_code"] == "stream_replay_expired"

    joined = client.post(
        f"/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{run_id}/join",
        headers=auth_headers(key),
    )
    assert joined.status_code == 200
    assert joined.json()["compat_response"]["status"] == "succeeded"
    assert runtime.run_store.runs[run_id].status == "succeeded"
    assert joined.json()["golden_record"]["expected_semantics"]["compat_status"] == "succeeded"

    cancelled = client.post(
        f"/v1/console/compatibility/langgraph/threads/{thread_id}/runs/{streamed_run_id}/cancel",
        headers=auth_headers(key),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["compat_response"]["status"] == "cancelled"
    assert (
        cancelled.json()["golden_record"]["expected_semantics"]["compat_status"]
        == "cancelled"
    )
