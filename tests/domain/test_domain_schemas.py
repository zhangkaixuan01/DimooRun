from dimoo_run.domain.enums import (
    AgentInstanceStatus,
    AuditActorType,
    DeploymentDesiredStatus,
    DeploymentRuntimeStatus,
    RunAttemptStatus,
    RunStatus,
    TaskStatus,
)
from dimoo_run.domain.schemas import DeploymentRead, ErrorResponse, RunRead


def test_status_enums_match_design_spec() -> None:
    assert [item.value for item in DeploymentDesiredStatus] == [
        "draft",
        "active",
        "paused",
        "draining",
        "stopped",
        "archived",
    ]
    assert [item.value for item in DeploymentRuntimeStatus] == [
        "not_loaded",
        "warming_up",
        "ready",
        "degraded",
        "failed",
        "draining",
        "stopped",
    ]
    assert [item.value for item in AgentInstanceStatus] == [
        "loading",
        "ready",
        "busy",
        "idle",
        "draining",
        "evicted",
        "failed",
    ]
    assert [item.value for item in RunStatus] == [
        "pending",
        "running",
        "interrupted",
        "succeeded",
        "failed",
        "cancelled",
        "timeout",
    ]
    assert [item.value for item in RunAttemptStatus] == [
        "running",
        "succeeded",
        "failed",
        "timeout",
        "cancelled",
        "worker_lost",
    ]
    assert [item.value for item in TaskStatus] == [
        "queued",
        "leased",
        "running",
        "retrying",
        "succeeded",
        "failed",
        "dead_letter",
        "cancelled",
    ]
    assert [item.value for item in AuditActorType] == [
        "user",
        "service_account",
        "system",
        "agent",
    ]


def test_deployment_schema_separates_desired_and_runtime_status() -> None:
    deployment = DeploymentRead(
        id=1,
        tenant_id=1,
        project_id=1,
        agent_id=1,
        agent_version_id=1,
        environment="local",
        desired_status=DeploymentDesiredStatus.active,
        runtime_status=DeploymentRuntimeStatus.ready,
        replicas=1,
    )

    assert deployment.desired_status == DeploymentDesiredStatus.active
    assert deployment.runtime_status == DeploymentRuntimeStatus.ready


def test_run_schema_keeps_nullable_service_account_id() -> None:
    run = RunRead(
        id=1,
        tenant_id=1,
        project_id=1,
        user_id=1,
        service_account_id=None,
        agent_id=1,
        agent_version_id=1,
        deployment_id=1,
        status=RunStatus.pending,
    )

    assert run.service_account_id is None


def test_error_response_uses_stable_error_code() -> None:
    error = ErrorResponse(
        error_code="deployment_not_accepting_runs",
        message="Deployment is not accepting new runs.",
        request_id="req_123",
        details={"deployment_id": "dep_1"},
    )

    assert error.error_code == "deployment_not_accepting_runs"
    assert error.details == {"deployment_id": "dep_1"}
