import os
import tempfile
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.deployments import reset_deployment_control
from dimoo_run.api.native.runtime import reset_native_runtime
from dimoo_run.domain.enums import RunStatus, TaskStatus
from dimoo_run.domain.models import BatchRuns, Run, ScheduledRuns, Task
from dimoo_run.packages.validation import validation_token
from dimoo_run.persistence.database import Base, create_session_factory
from dimoo_run.server import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DIMOORUN_DEV_API_KEY"] = "dev-local-key"
    os.environ["DIMOORUN_NATIVE_RUNTIME_STORE"] = "sqlalchemy"
    os.environ["DATABASE_URL"] = (
        f"sqlite:///{tempfile.gettempdir()}/dimoorun-scheduled-batch-{uuid4().hex}.db"
    )
    reset_api_key_authenticator()
    reset_deployment_control()
    reset_native_runtime()
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)


def teardown_function() -> None:
    reset_api_key_authenticator()
    reset_deployment_control()
    reset_native_runtime()


def create_api_key() -> str:
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="runtime-batch",
        permissions={"agent:create", "agent:deploy", "agent:invoke", "agent:read", "agent:write"},
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="runtime-batch-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes={"agent:create", "agent:deploy", "agent:invoke", "agent:read", "agent:write"},
        created_by="admin_1",
    )
    return plain_key


def native_headers(api_key: str, request_id: str, environment: str = "local") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": request_id,
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": environment,
    }


def admin_headers(request_id: str, environment: str = "local") -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Request-Id": request_id,
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": environment,
    }


def create_deployment(client: TestClient, api_key: str, environment: str = "local") -> int:
    agent = client.post(
        "/v1/agents",
        headers=native_headers(api_key, "req_agent_create", environment),
        json={"name": f"schedule-agent-{environment}"},
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]
    version = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=native_headers(api_key, "req_version_create", environment),
        json={
            "version": "0.1.0",
            "package_uri": "file://scheduled-agent",
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
                    package_uri="file://scheduled-agent",
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
    deployment = client.post(
        "/v1/deployments",
        headers=native_headers(api_key, "req_deployment_create", environment),
        json={
            "agent_id": agent_id,
            "agent_version_id": version.json()["id"],
            "environment": environment,
            "desired_status": "active",
            "replicas": 1,
        },
    )
    assert deployment.status_code == 201
    return int(deployment.json()["id"])


def test_scheduled_and_batch_paths_are_registered() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    for path in [
        "/v1/schedules/preview",
        "/v1/schedules",
        "/v1/schedules/run-due",
        "/v1/schedules/{schedule_id}",
        "/v1/schedules/{schedule_id}/pause",
        "/v1/schedules/{schedule_id}/resume",
        "/v1/schedules/{schedule_id}/trigger",
        "/v1/batch-runs",
        "/v1/batch-runs/{batch_id}",
        "/v1/batch-runs/{batch_id}/cancel",
    ]:
        assert path in paths


def test_schedule_preview_validates_timezone_and_returns_next_fire_time() -> None:
    client = TestClient(create_app())

    invalid = client.post(
        "/v1/schedules/preview",
        headers=admin_headers("req_schedule_preview_invalid"),
        json={"interval_minutes": 15, "timezone": "Mars/Phobos"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error_code"] == "invalid_timezone"

    valid = client.post(
        "/v1/schedules/preview",
        headers=admin_headers("req_schedule_preview_valid"),
        json={"interval_minutes": 15, "timezone": "UTC", "deployment_id": 1},
    )
    assert valid.status_code == 200
    body = valid.json()
    assert body["preview"]["schedule_type"] == "interval"
    assert body["preview"]["timezone"] == "UTC"
    assert body["preview"]["next_fire_time"]


def test_schedule_create_pause_resume_and_trigger_persists_and_enqueues_run() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    deployment_id = create_deployment(client, api_key)

    created = client.post(
        "/v1/schedules",
        headers=admin_headers("req_schedule_create"),
        json={
            "name": "nightly-eval",
            "interval_minutes": 30,
            "timezone": "UTC",
            "deployment_id": deployment_id,
            "input_template": {"message": "scheduled"},
            "backfill_policy": "latest",
            "missed_run_policy": "run_once",
            "audit_reason": "create nightly schedule",
        },
    )
    assert created.status_code == 201
    schedule_id = created.json()["item"]["id"]
    assert created.json()["item"]["deployment_id"] == deployment_id

    paused = client.post(
        f"/v1/schedules/{schedule_id}/pause",
        headers=admin_headers("req_schedule_pause"),
        json={"audit_reason": "freeze automation", "pause_reason": "maintenance"},
    )
    assert paused.status_code == 200
    assert paused.json()["item"]["status"] == "paused"
    assert paused.json()["item"]["pause_reason"] == "maintenance"

    resumed = client.post(
        f"/v1/schedules/{schedule_id}/resume",
        headers=admin_headers("req_schedule_resume"),
        json={"audit_reason": "resume automation"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["item"]["status"] == "active"

    triggered = client.post(
        f"/v1/schedules/{schedule_id}/trigger",
        headers=admin_headers("req_schedule_trigger"),
        json={"audit_reason": "manual trigger"},
    )
    assert triggered.status_code == 200
    assert triggered.json()["triggered_run"]["status"] == "queued"
    assert triggered.json()["item"]["last_run_id"] > 0
    assert triggered.json()["item"]["last_task_id"] > 0

    session = create_session_factory(os.environ["DATABASE_URL"])()
    try:
        record = session.get(ScheduledRuns, schedule_id)
        run = session.get(Run, triggered.json()["item"]["last_run_id"])
        task = session.get(Task, triggered.json()["item"]["last_task_id"])
        assert record is not None
        assert run is not None
        assert task is not None
        assert record.metadata_json["name"] == "nightly-eval"
    finally:
        session.close()

    session = create_session_factory(os.environ["DATABASE_URL"])()
    try:
        run = session.get(Run, triggered.json()["item"]["last_run_id"])
        task = session.get(Task, triggered.json()["item"]["last_task_id"])
        assert run is not None
        assert task is not None
        run.status = RunStatus.succeeded.value
        task.status = TaskStatus.succeeded.value
        session.commit()
    finally:
        session.close()

    refreshed = client.get(
        f"/v1/schedules/{schedule_id}",
        headers=admin_headers("req_schedule_get"),
    )
    assert refreshed.status_code == 200
    refreshed_item = refreshed.json()["item"]
    assert refreshed_item["trigger_count"] == 1
    assert refreshed_item["last_trigger_source"] == "manual"
    assert refreshed_item["last_run_status"] == "succeeded"
    assert refreshed_item["last_task_status"] == "succeeded"


def test_run_due_schedules_respects_skip_run_once_and_catch_up_policies() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    deployment_id = create_deployment(client, api_key)

    created_ids: dict[str, int] = {}
    for name, missed_run_policy in [
        ("skip-me", "skip"),
        ("run-once", "run_once"),
        ("catch-up", "catch_up"),
    ]:
        created = client.post(
            "/v1/schedules",
            headers=admin_headers(f"req_schedule_create_{name}"),
            json={
                "name": name,
                "interval_minutes": 30,
                "timezone": "UTC",
                "deployment_id": deployment_id,
                "input_template": {"message": name},
                "backfill_policy": "latest",
                "missed_run_policy": missed_run_policy,
                "audit_reason": f"create {name}",
            },
        )
        assert created.status_code == 201
        created_ids[name] = int(created.json()["item"]["id"])

    session = create_session_factory(os.environ["DATABASE_URL"])()
    try:
        overdue = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        for schedule_id in created_ids.values():
            record = session.get(ScheduledRuns, schedule_id)
            assert record is not None
            metadata = dict(record.metadata_json)
            metadata["next_fire_time"] = overdue
            record.metadata_json = metadata
        session.commit()
    finally:
        session.close()

    due = client.post(
        "/v1/schedules/run-due",
        headers=admin_headers("req_schedule_run_due"),
        json={"audit_reason": "advance due schedules"},
    )
    assert due.status_code == 200
    body = due.json()
    assert body["count"] == 2
    triggered = {entry["schedule_id"]: entry for entry in body["triggered"]}
    skipped = {entry["schedule_id"]: entry for entry in body["skipped"]}
    assert created_ids["skip-me"] in skipped
    assert created_ids["run-once"] in triggered
    assert created_ids["catch-up"] in triggered
    assert triggered[created_ids["run-once"]]["triggered_count"] == 1
    assert triggered[created_ids["catch-up"]]["triggered_count"] >= 2

    refreshed_skip = client.get(
        f"/v1/schedules/{created_ids['skip-me']}",
        headers=admin_headers("req_schedule_skip_get"),
    )
    refreshed_once = client.get(
        f"/v1/schedules/{created_ids['run-once']}",
        headers=admin_headers("req_schedule_once_get"),
    )
    refreshed_catch_up = client.get(
        f"/v1/schedules/{created_ids['catch-up']}",
        headers=admin_headers("req_schedule_catchup_get"),
    )
    assert refreshed_skip.status_code == 200
    assert refreshed_once.status_code == 200
    assert refreshed_catch_up.status_code == 200
    assert refreshed_skip.json()["item"]["trigger_count"] == 0
    assert refreshed_once.json()["item"]["trigger_count"] == 1
    assert refreshed_once.json()["item"]["last_trigger_source"] == "automatic"
    assert refreshed_catch_up.json()["item"]["trigger_count"] >= 2
    assert refreshed_catch_up.json()["item"]["last_trigger_source"] == "automatic"
    assert refreshed_once.json()["item"]["last_task_id"] > 0
    assert refreshed_catch_up.json()["item"]["last_task_id"] > 0


def test_batch_create_supports_partial_failure_and_cancel() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    deployment_id = create_deployment(client, api_key)

    created = client.post(
        "/v1/batch-runs",
        headers=admin_headers("req_batch_create"),
        json={
            "name": "backfill-failed-runs",
            "deployment_id": deployment_id,
            "input_items": [{"message": "one"}, "bad-item", {"message": "two"}],
            "concurrency": 2,
            "retry_policy": {"max_attempts": 2},
            "cancel_policy": "best_effort",
            "partial_failure_policy": "continue",
            "audit_reason": "backfill failures",
        },
    )
    assert created.status_code == 201
    body = created.json()["item"]
    assert body["status"] == "partial_failed"
    assert body["progress_summary"]["total_items"] == 3
    assert body["progress_summary"]["queued_items"] == 2
    assert body["progress_summary"]["failed_items"] == 1

    cancelled = client.post(
        f"/v1/batch-runs/{body['id']}/cancel",
        headers=admin_headers("req_batch_cancel"),
        json={"audit_reason": "stop backfill"},
    )
    assert cancelled.status_code == 200
    cancelled_body = cancelled.json()["item"]
    assert cancelled_body["progress_summary"]["cancelled_items"] == 2
    assert cancelled_body["progress_summary"]["failed_items"] == 1

    session = create_session_factory(os.environ["DATABASE_URL"])()
    try:
        queued_tasks = session.query(Task).all()
        assert len(queued_tasks) == 2
        assert all(task.status == "cancelled" for task in queued_tasks)
    finally:
        session.close()


def test_batch_detail_recomputes_retry_dead_letter_and_completion_summary_from_tasks() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    deployment_id = create_deployment(client, api_key)

    created = client.post(
        "/v1/batch-runs",
        headers=admin_headers("req_batch_state_machine_create"),
        json={
            "name": "state-machine-batch",
            "deployment_id": deployment_id,
            "input_items": [{"message": "one"}, {"message": "two"}, {"message": "three"}],
            "concurrency": 3,
            "retry_policy": {"max_attempts": 2},
            "cancel_policy": "best_effort",
            "partial_failure_policy": "continue",
            "audit_reason": "exercise runtime summary",
        },
    )
    assert created.status_code == 201
    batch_id = created.json()["item"]["id"]

    session = create_session_factory(os.environ["DATABASE_URL"])()
    try:
        record = session.get(BatchRuns, batch_id)
        assert record is not None
        items = list(record.metadata_json["items"])
        task_ids = [int(item["task_id"]) for item in items]
        tasks = [session.get(Task, task_id) for task_id in task_ids]
        assert all(task is not None for task in tasks)
        tasks[0].status = TaskStatus.retrying.value  # type: ignore[union-attr]
        tasks[1].status = TaskStatus.dead_letter.value  # type: ignore[union-attr]
        tasks[1].dead_letter_reason = "retry_exhausted"  # type: ignore[union-attr]
        tasks[2].status = TaskStatus.succeeded.value  # type: ignore[union-attr]
        session.commit()
    finally:
        session.close()

    detail = client.get(
        f"/v1/batch-runs/{batch_id}",
        headers=admin_headers("req_batch_state_machine_detail"),
    )
    assert detail.status_code == 200
    item = detail.json()["item"]
    assert item["status"] == "running"
    assert item["progress_summary"]["queued_items"] == 0
    assert item["progress_summary"]["running_items"] == 0
    assert item["progress_summary"]["retrying_items"] == 1
    assert item["progress_summary"]["dead_letter_items"] == 1
    assert item["progress_summary"]["completed_items"] == 1
    assert item["progress_summary"]["terminal_items"] == 2
    statuses = [entry["status"] for entry in item["items"]]
    assert statuses == ["retrying", "dead_letter", "succeeded"]
    assert item["items"][1]["message"] == "retry_exhausted"


def test_batch_detail_marks_completed_when_all_tasks_are_terminal() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    deployment_id = create_deployment(client, api_key)

    created = client.post(
        "/v1/batch-runs",
        headers=admin_headers("req_batch_completed_create"),
        json={
            "name": "completed-batch",
            "deployment_id": deployment_id,
            "input_items": [{"message": "one"}, {"message": "two"}],
            "concurrency": 2,
            "retry_policy": {"max_attempts": 2},
            "cancel_policy": "best_effort",
            "partial_failure_policy": "continue",
            "audit_reason": "exercise completion summary",
        },
    )
    assert created.status_code == 201
    batch_id = created.json()["item"]["id"]

    session = create_session_factory(os.environ["DATABASE_URL"])()
    try:
        record = session.get(BatchRuns, batch_id)
        assert record is not None
        for item in list(record.metadata_json["items"]):
            task = session.get(Task, int(item["task_id"]))
            assert task is not None
            task.status = TaskStatus.succeeded.value
        session.commit()
    finally:
        session.close()

    detail = client.get(
        f"/v1/batch-runs/{batch_id}",
        headers=admin_headers("req_batch_completed_detail"),
    )
    assert detail.status_code == 200
    item = detail.json()["item"]
    assert item["status"] == "completed"
    assert item["progress_summary"]["completed_items"] == 2
    assert item["progress_summary"]["terminal_items"] == 2


def test_schedule_detail_exposes_hardened_runtime_fields() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    deployment_id = create_deployment(client, api_key)

    created = client.post(
        "/v1/schedules",
        headers=admin_headers("req_schedule_hardened_create"),
        json={
            "name": "hardened-schedule",
            "interval_minutes": 15,
            "timezone": "UTC",
            "deployment_id": deployment_id,
            "input_template": {"message": "scheduled"},
            "backfill_policy": "latest",
            "missed_run_policy": "run_once",
            "audit_reason": "create hardened schedule",
        },
    )
    assert created.status_code == 201

    response = client.get(
        f"/v1/schedules/{created.json()['item']['id']}",
        headers=admin_headers("req_schedule_detail"),
    )
    assert response.status_code == 200
    body = response.json()["item"]
    assert "next_fire_time" in body
    assert "next_fire_at" in body
    assert "trigger_count" in body
    assert "pause_reason" in body
    assert body["schedule_type"] == "interval"
    assert body["timezone"] == "UTC"
    assert body["missed_run_policy"] == "run_once"
    assert body["backfill_policy"] == "latest"


def test_batch_detail_exposes_hardened_summary_fields() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    deployment_id = create_deployment(client, api_key)

    created = client.post(
        "/v1/batch-runs",
        headers=admin_headers("req_batch_hardened_create"),
        json={
            "name": "hardened-batch",
            "deployment_id": deployment_id,
            "input_items": [{"message": "one"}, "bad-item", {"message": "two"}],
            "concurrency": 2,
            "retry_policy": {"max_attempts": 2},
            "cancel_policy": "best_effort",
            "partial_failure_policy": "continue",
            "audit_reason": "create hardened batch",
        },
    )
    assert created.status_code == 201

    response = client.get(
        f"/v1/batch-runs/{created.json()['item']['id']}",
        headers=admin_headers("req_batch_detail"),
    )
    assert response.status_code == 200
    body = response.json()["item"]
    for key in [
        "deployment_id",
        "total_items",
        "queued_items",
        "completed_items",
        "failed_items",
        "dead_letter_items",
    ]:
        assert key in body
    assert body["deployment_id"] == deployment_id
    assert body["total_items"] == 3
    assert body["queued_items"] == 2
    assert body["failed_items"] == 1
