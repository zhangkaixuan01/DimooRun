from dimoo_run.api.compat.langgraph import default_compat_runtime, reset_compat_runtime
from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.deployments import default_deployment_control, reset_deployment_control
from dimoo_run.deployments.service import DeploymentRecord
from dimoo_run.domain.enums import DeploymentDesiredStatus
from dimoo_run.identity.service_accounts import ServiceAccountRecord
from dimoo_run.server import create_app
from fastapi.testclient import TestClient

COMPAT_PATHS = [
    "/compat/langgraph/assistants",
    "/compat/langgraph/assistants/{assistant_id}",
    "/compat/langgraph/threads",
    "/compat/langgraph/threads/{thread_id}",
    "/compat/langgraph/threads/{thread_id}/runs",
    "/compat/langgraph/threads/{thread_id}/runs/{run_id}",
    "/compat/langgraph/threads/{thread_id}/runs/{run_id}/cancel",
    "/compat/langgraph/threads/{thread_id}/runs/{run_id}/join",
    "/compat/langgraph/threads/{thread_id}/runs/stream",
    "/compat/agent-protocol/capabilities",
]


def setup_function() -> None:
    reset_api_key_authenticator()
    reset_compat_runtime()
    reset_deployment_control()


def create_api_key(*, scopes: set[str] | None = None) -> tuple[str, ServiceAccountRecord]:
    requested_scopes = scopes or {"agent:read", "agent:invoke"}
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id="tenant_1",
        project_id="project_1",
        name="compat",
        permissions=requested_scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id="tenant_1",
        project_id="project_1",
        name="compat-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=requested_scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def auth_headers(api_key: str | None = None) -> dict[str, str]:
    key = api_key or create_api_key()[0]
    return {
        "Authorization": f"Bearer {key}",
        "X-Request-Id": "req_compat",
        "X-Tenant-Id": "tenant_1",
        "X-Project-Id": "project_1",
    }


def test_langgraph_compat_paths_are_registered() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in COMPAT_PATHS:
        assert path in paths


def test_langgraph_compat_requires_api_key() -> None:
    client = TestClient(create_app())

    response = client.get("/compat/langgraph/assistants")

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_key_invalid"


def test_langgraph_compat_rejects_unregistered_bearer_token() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/compat/langgraph/assistants",
        headers={
            "Authorization": "Bearer anything",
            "X-Tenant-Id": "tenant_1",
            "X-Project-Id": "project_1",
        },
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_key_invalid"


def test_langgraph_compat_assistant_thread_run_flow_returns_sdk_shaped_objects() -> None:
    client = TestClient(create_app())
    key, service_account = create_api_key()

    assistant = client.post(
        "/compat/langgraph/assistants",
        headers=auth_headers(key),
        json={"name": "support-agent", "deployment_id": "dep_prod_support"},
    )
    assert assistant.status_code == 201
    assistant_body = assistant.json()
    assert assistant_body["assistant_id"].startswith("assistant_")
    assert assistant_body["metadata"]["dimoorun_mapping"]["deployment_id"] == "dep_prod_support"

    listed_assistants = client.get(
        "/compat/langgraph/assistants",
        headers=auth_headers(key),
    ).json()["assistants"]
    assert listed_assistants

    thread = client.post("/compat/langgraph/threads", headers=auth_headers(key), json={})
    assert thread.status_code == 201
    thread_id = thread.json()["thread_id"]

    run = client.post(
        f"/compat/langgraph/threads/{thread_id}/runs",
        headers=auth_headers(key),
        json={"assistant_id": assistant_body["assistant_id"], "input": {"message": "hello"}},
    )
    assert run.status_code == 201
    run_body = run.json()
    assert run_body["run_id"].startswith("run_")
    assert run_body["status"] == "queued"
    assert run_body["metadata"]["dimoorun_mapping"]["task_id"].startswith("task_")
    runtime = default_compat_runtime()
    assert run_body["metadata"]["dimoorun_mapping"]["task_id"] in runtime.task_backend.tasks
    assert run_body["metadata"]["dimoorun_mapping"]["run_id"] in runtime.run_store.runs
    assert runtime.audit_log.records[-1].actor_id == service_account.id

    joined = client.post(
        f"/compat/langgraph/threads/{thread_id}/runs/{run_body['run_id']}/join",
        headers=auth_headers(key),
    )
    assert joined.status_code == 200
    assert joined.json()["status"] == "succeeded"
    assert runtime.run_store.runs[run_body["run_id"]].status == "succeeded"
    assert runtime.audit_log.records[-1].action == "compat.langgraph.run.join"

    stream = client.post(
        f"/compat/langgraph/threads/{thread_id}/runs/stream",
        headers=auth_headers(key),
        json={"assistant_id": assistant_body["assistant_id"], "input": {"message": "hello"}},
    )
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "event: run.created" in stream.text
    assert "event: task.queued" in stream.text
    assert "event: run.started" in stream.text
    streamed_run_id = stream.text.split("id: ", maxsplit=1)[1].split(":", maxsplit=1)[0]
    assert runtime.run_store.runs[streamed_run_id].status == "running"


def test_langgraph_compat_cancel_updates_runtime_run_task_and_audit() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    assistant = client.post(
        "/compat/langgraph/assistants",
        headers=auth_headers(key),
        json={"name": "support-agent", "deployment_id": "dep_prod_support"},
    ).json()
    thread = client.post("/compat/langgraph/threads", headers=auth_headers(key), json={}).json()
    run = client.post(
        f"/compat/langgraph/threads/{thread['thread_id']}/runs",
        headers=auth_headers(key),
        json={"assistant_id": assistant["assistant_id"], "input": {"message": "hello"}},
    ).json()

    response = client.post(
        f"/compat/langgraph/threads/{thread['thread_id']}/runs/{run['run_id']}/cancel",
        headers=auth_headers(key),
    )

    runtime = default_compat_runtime()
    task_id = run["metadata"]["dimoorun_mapping"]["task_id"]
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert runtime.run_store.runs[run["run_id"]].status == "cancelled"
    assert runtime.task_backend.tasks[task_id].status == "cancelled"
    assert runtime.audit_log.records[-1].action == "compat.langgraph.run.cancel"


def test_langgraph_compat_respects_deployment_gate_when_deployment_exists() -> None:
    service = default_deployment_control()
    service.deployments.add(
        DeploymentRecord(
            id="deployment_paused",
            tenant_id="tenant_1",
            project_id="project_1",
            agent_id="support-agent",
            agent_version_id="compat-langgraph",
            environment="dev",
            desired_status=DeploymentDesiredStatus.paused,
        )
    )
    client = TestClient(create_app())
    key, _ = create_api_key()
    assistant = client.post(
        "/compat/langgraph/assistants",
        headers=auth_headers(key),
        json={"name": "support-agent", "deployment_id": "deployment_paused"},
    ).json()
    thread = client.post("/compat/langgraph/threads", headers=auth_headers(key), json={}).json()

    response = client.post(
        f"/compat/langgraph/threads/{thread['thread_id']}/runs",
        headers=auth_headers(key),
        json={"assistant_id": assistant["assistant_id"], "input": {"message": "hello"}},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "deployment_not_accepting_runs"


def test_langgraph_compat_rejects_cross_scope_existing_deployment() -> None:
    service = default_deployment_control()
    service.deployments.add(
        DeploymentRecord(
            id="deployment_other",
            tenant_id="tenant_2",
            project_id="project_2",
            agent_id="support-agent",
            agent_version_id="compat-langgraph",
            environment="dev",
            desired_status=DeploymentDesiredStatus.active,
        )
    )
    client = TestClient(create_app())
    key, _ = create_api_key()
    response = client.post(
        "/compat/langgraph/assistants",
        headers=auth_headers(key),
        json={"name": "support-agent", "deployment_id": "deployment_other"},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "deployment_not_found"


def test_stream_run_validates_thread_and_assistant_mapping() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()

    missing_thread = client.post(
        "/compat/langgraph/threads/missing/runs/stream",
        headers=auth_headers(key),
        json={"assistant_id": "missing", "input": {}},
    )

    assert missing_thread.status_code == 404
    assert missing_thread.json()["error_code"] == "thread_not_found"


def test_langgraph_compat_does_not_allow_cross_project_thread_or_assistant_binding() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key()
    cross_key, _ = create_api_key_for_scope(
        tenant_id="tenant_2",
        project_id="project_2",
        scopes={"agent:read", "agent:invoke"},
    )
    assistant = client.post(
        "/compat/langgraph/assistants",
        headers=auth_headers(key),
        json={"name": "support-agent", "deployment_id": "dep_prod_support"},
    ).json()
    thread = client.post("/compat/langgraph/threads", headers=auth_headers(key), json={}).json()

    response = client.post(
        f"/compat/langgraph/threads/{thread['thread_id']}/runs",
        headers=auth_headers_for_scope(cross_key, tenant_id="tenant_2", project_id="project_2"),
        json={"assistant_id": assistant["assistant_id"], "input": {"message": "hello"}},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "thread_not_found"


def test_agent_protocol_declares_unsupported_capability_with_stable_error() -> None:
    client = TestClient(create_app())

    response = client.get("/compat/agent-protocol/capabilities", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["unsupported_error_code"] == "compatibility_not_supported"


def test_agent_protocol_capabilities_only_require_read_scope() -> None:
    client = TestClient(create_app())
    key, _ = create_api_key(scopes={"agent:read"})

    response = client.get("/compat/agent-protocol/capabilities", headers=auth_headers(key))

    assert response.status_code == 200


def create_api_key_for_scope(
    *,
    tenant_id: str,
    project_id: str,
    scopes: set[str],
) -> tuple[str, ServiceAccountRecord]:
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=tenant_id,
        project_id=project_id,
        name="compat",
        permissions=scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=tenant_id,
        project_id=project_id,
        name="compat-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=scopes,
        created_by="admin_1",
    )
    return plain_key, service_account


def auth_headers_for_scope(api_key: str, *, tenant_id: str, project_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": "req_compat",
        "X-Tenant-Id": tenant_id,
        "X-Project-Id": project_id,
    }
