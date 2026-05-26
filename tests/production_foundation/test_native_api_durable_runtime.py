from collections.abc import Iterator

from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.runtime import (
    SQLAlchemyNativeRuntimeStore,
    reset_native_runtime,
    set_default_native_runtime,
)
from dimoo_run.domain.models import Agent, AuditLog, Deployment, Event, Run, Task
from dimoo_run.persistence.database import Base
from dimoo_run.runtime.state_machine import InvalidStateTransitionError
from dimoo_run.server import create_app
from fastapi.testclient import TestClient
from pytest import fixture
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@fixture()
def durable_client() -> Iterator[tuple[TestClient, Session, str]]:
    reset_api_key_authenticator()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    set_default_native_runtime(SQLAlchemyNativeRuntimeStore(session))
    authenticator = default_api_key_authenticator()
    scopes = {"agent:read", "agent:write", "agent:invoke", "agent:deploy"}
    service_account = authenticator.service_accounts.create(
        tenant_id="tenant_1",
        project_id="project_1",
        name="native",
        permissions=scopes,
        created_by="admin_1",
    )
    api_key, _ = authenticator.create_key(
        tenant_id="tenant_1",
        project_id="project_1",
        name="native-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=scopes,
        created_by="admin_1",
    )
    try:
        yield TestClient(create_app()), session, api_key
    finally:
        reset_native_runtime()
        session.close()


def auth_headers(api_key: str, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": "req_durable",
        "X-Tenant-Id": "tenant_1",
        "X-Project-Id": "project_1",
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def test_native_api_can_use_sqlalchemy_runtime_store(
    durable_client: tuple[TestClient, Session, str],
) -> None:
    client, session, api_key = durable_client
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(api_key),
        json={"name": "support-agent"},
    ).json()
    version = client.post(
        f"/v1/agents/{agent['id']}/versions",
        headers=auth_headers(api_key),
        json={"version": "0.1.0", "package_uri": "file://support-agent"},
    ).json()
    task_response = client.post(
        f"/v1/agents/{agent['id']}/tasks",
        headers=auth_headers(api_key, idempotency_key="idem_1"),
        json={"input": {"message": "hello"}},
    )

    assert task_response.status_code == 202
    body = task_response.json()
    run = session.scalar(select(Run).where(Run.id == body["run_id"]))
    task = session.scalar(select(Task).where(Task.id == body["task_id"]))
    events = list(session.scalars(select(Event).where(Event.run_id == body["run_id"])))

    assert run is not None
    assert run.agent_id == agent["id"]
    assert run.agent_version_id == version["id"]
    assert task is not None
    assert task.run_id == run.id
    assert [event.type for event in events] == ["run.created", "task.queued"]


def test_native_api_durable_runtime_replays_idempotent_create(
    durable_client: tuple[TestClient, Session, str],
) -> None:
    client, _, api_key = durable_client
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(api_key),
        json={"name": "support-agent"},
    ).json()
    client.post(
        f"/v1/agents/{agent['id']}/versions",
        headers=auth_headers(api_key),
        json={"version": "0.1.0"},
    )

    first = client.post(
        f"/v1/agents/{agent['id']}/tasks",
        headers=auth_headers(api_key, idempotency_key="idem_1"),
        json={"input": {"message": "hello"}},
    )
    second = client.post(
        f"/v1/agents/{agent['id']}/tasks",
        headers=auth_headers(api_key, idempotency_key="idem_1"),
        json={"input": {"message": "hello"}},
    )

    assert second.status_code == 202
    assert second.json()["run_id"] == first.json()["run_id"]
    assert second.json()["task_id"] == first.json()["task_id"]
    assert second.json()["replayed"] is True


def test_native_api_updates_and_archives_agent_in_sqlalchemy_runtime(
    durable_client: tuple[TestClient, Session, str],
) -> None:
    client, session, api_key = durable_client
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(api_key),
        json={"name": "support-agent"},
    ).json()

    updated = client.patch(
        f"/v1/agents/{agent['id']}",
        headers=auth_headers(api_key),
        json={"name": "support-agent-v2", "description": "updated"},
    )
    deleted = client.delete(
        f"/v1/agents/{agent['id']}",
        headers=auth_headers(api_key),
    )
    model = session.get(Agent, agent["id"])

    assert updated.status_code == 200
    assert updated.json()["name"] == "support-agent-v2"
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "archived"
    assert model is not None
    assert model.name == "support-agent-v2"
    assert model.status == "archived"
    assert model.is_deleted is True


def test_native_api_cancel_responses_reflect_sqlalchemy_state(
    durable_client: tuple[TestClient, Session, str],
) -> None:
    client, session, api_key = durable_client
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(api_key),
        json={"name": "support-agent"},
    ).json()
    client.post(
        f"/v1/agents/{agent['id']}/versions",
        headers=auth_headers(api_key),
        json={"version": "0.1.0"},
    )
    task_response = client.post(
        f"/v1/agents/{agent['id']}/tasks",
        headers=auth_headers(api_key),
        json={"input": {"message": "hello"}},
    ).json()

    cancelled_run = client.post(
        f"/v1/runs/{task_response['run_id']}/cancel",
        headers=auth_headers(api_key),
    )
    cancelled_task = client.post(
        f"/v1/tasks/{task_response['task_id']}/cancel",
        headers=auth_headers(api_key),
    )
    run = session.get(Run, task_response["run_id"])
    task = session.get(Task, task_response["task_id"])

    assert cancelled_run.status_code == 200
    assert cancelled_run.json()["status"] == "cancelled"
    assert cancelled_task.status_code == 200
    assert cancelled_task.json()["status"] == "cancelled"
    assert run is not None
    assert run.status == "cancelled"
    assert task is not None
    assert task.status == "cancelled"


def test_native_api_cancel_uses_runtime_state_machine(
    durable_client: tuple[TestClient, Session, str],
) -> None:
    client, session, api_key = durable_client
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(api_key),
        json={"name": "support-agent"},
    ).json()
    client.post(
        f"/v1/agents/{agent['id']}/versions",
        headers=auth_headers(api_key),
        json={"version": "0.1.0"},
    )
    task_response = client.post(
        f"/v1/agents/{agent['id']}/tasks",
        headers=auth_headers(api_key),
        json={"input": {"message": "hello"}},
    ).json()
    run = session.get(Run, task_response["run_id"])
    assert run is not None
    run.status = "succeeded"
    session.flush()

    try:
        client.post(
            f"/v1/runs/{task_response['run_id']}/cancel",
            headers=auth_headers(api_key),
        )
    except InvalidStateTransitionError as exc:
        assert exc.current == "succeeded"
        assert exc.target == "cancelled"
    else:
        raise AssertionError("Expected invalid state transition")


def test_native_api_exposes_dead_letter_task_details(
    durable_client: tuple[TestClient, Session, str],
) -> None:
    client, session, api_key = durable_client
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(api_key),
        json={"name": "support-agent"},
    ).json()
    client.post(
        f"/v1/agents/{agent['id']}/versions",
        headers=auth_headers(api_key),
        json={"version": "0.1.0"},
    )
    task_response = client.post(
        f"/v1/agents/{agent['id']}/tasks",
        headers=auth_headers(api_key),
        json={"input": {"message": "hello"}},
    ).json()
    task = session.get(Task, task_response["task_id"])
    assert task is not None
    task.status = "dead_letter"
    task.error = "boom"
    task.dead_letter_reason = "boom"
    session.flush()

    response = client.get(
        f"/v1/tasks/{task_response['task_id']}",
        headers=auth_headers(api_key),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dead_letter"
    assert body["error"] == {"message": "boom"}
    assert body["dead_letter_reason"] == "boom"


def test_native_api_exposes_task_runtime_scheduling_details(
    durable_client: tuple[TestClient, Session, str],
) -> None:
    client, session, api_key = durable_client
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(api_key),
        json={"name": "support-agent"},
    ).json()
    client.post(
        f"/v1/agents/{agent['id']}/versions",
        headers=auth_headers(api_key),
        json={"version": "0.1.0"},
    )
    task_response = client.post(
        f"/v1/agents/{agent['id']}/tasks",
        headers=auth_headers(api_key),
        json={"input": {"message": "hello"}},
    ).json()
    task = session.get(Task, task_response["task_id"])
    assert task is not None
    task.metadata_json = {
        "partition_key": "tenant_1:project_1",
        "resource_class": "gpu",
        "quota_blocking_reason": {
            "error_code": "runtime_quota_exceeded",
            "scope": "project",
            "limit": 1,
            "current": 1,
        },
    }
    session.flush()

    response = client.get(
        f"/v1/tasks/{task_response['task_id']}",
        headers=auth_headers(api_key),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["partition_key"] == "tenant_1:project_1"
    assert body["resource_class"] == "gpu"
    assert body["quota_blocking_reason"]["scope"] == "project"


def test_native_api_uses_request_scoped_sqlalchemy_runtime_from_env(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    reset_api_key_authenticator()
    database_path = tmp_path / "runtime.db"
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DIMOORUN_NATIVE_RUNTIME_STORE", "sqlalchemy")
    monkeypatch.setenv("DATABASE_URL", database_url)
    authenticator = default_api_key_authenticator()
    scopes = {"agent:read", "agent:write", "agent:invoke", "agent:deploy"}
    service_account = authenticator.service_accounts.create(
        tenant_id="tenant_1",
        project_id="project_1",
        name="native",
        permissions=scopes,
        created_by="admin_1",
    )
    api_key, _ = authenticator.create_key(
        tenant_id="tenant_1",
        project_id="project_1",
        name="native-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=scopes,
        created_by="admin_1",
    )
    client = TestClient(create_app())

    agent = client.post(
        "/v1/agents",
        headers=auth_headers(api_key),
        json={"name": "support-agent"},
    ).json()
    client.post(
        f"/v1/agents/{agent['id']}/versions",
        headers=auth_headers(api_key),
        json={"version": "0.1.0"},
    )
    task_response = client.post(
        f"/v1/agents/{agent['id']}/tasks",
        headers=auth_headers(api_key),
        json={"input": {"message": "hello"}},
    )
    deployment_response = client.post(
        "/v1/deployments",
        headers=auth_headers(api_key),
        json={
            "agent_id": agent["id"],
            "agent_version_id": client.get(
                f"/v1/agents/{agent['id']}/versions",
                headers=auth_headers(api_key),
            ).json()[0]["id"],
            "environment": "dev",
            "replicas": 2,
            "config": {"model_gateway": "default"},
        },
    )
    activate_response = client.post(
        f"/v1/deployments/{deployment_response.json()['id']}/activate",
        headers=auth_headers(api_key),
    )

    with Session(engine) as session:
        run = session.scalar(select(Run).where(Run.id == task_response.json()["run_id"]))
        task = session.scalar(select(Task).where(Task.id == task_response.json()["task_id"]))
        deployment = session.scalar(
            select(Deployment).where(Deployment.id == deployment_response.json()["id"])
        )
        audit = session.scalar(
            select(AuditLog).where(AuditLog.resource_id == deployment_response.json()["id"])
        )

    assert task_response.status_code == 202
    assert deployment_response.status_code == 201
    assert activate_response.status_code == 200
    assert activate_response.json()["desired_status"] == "active"
    assert run is not None
    assert task is not None
    assert deployment is not None
    assert deployment.desired_status == "active"
    assert deployment.config_json == {"model_gateway": "default"}
    assert audit is not None
