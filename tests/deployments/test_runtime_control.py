import pytest
from dimoo_run.deployments.service import (
    AllowAllPolicyEngine,
    DeploymentRecord,
    DeploymentRuntimeControlService,
    InMemoryAuditSink,
    InMemoryDeploymentStore,
    PolicyDeniedError,
    StaticPolicyEngine,
)
from dimoo_run.domain.enums import DeploymentDesiredStatus, DeploymentRuntimeStatus
from dimoo_run.runtime.run_manager import InMemoryRunStore, RunManager
from dimoo_run.scheduler.in_memory import InMemoryTaskBackend


def create_service() -> tuple[DeploymentRuntimeControlService, InMemoryDeploymentStore]:
    store = InMemoryDeploymentStore()
    store.add(
        DeploymentRecord(
            id=1,
            tenant_id=1,
            project_id=1,
            agent_id=1,
            agent_version_id=1,
            environment="dev",
        )
    )
    return (
        DeploymentRuntimeControlService(
            deployments=store,
            policy_engine=AllowAllPolicyEngine(),
            audit_sink=InMemoryAuditSink(),
        ),
        store,
    )


def test_deployment_control_actions_update_desired_status_and_audit() -> None:
    service, store = create_service()

    activated = service.activate(
        1,
        actor_id="1",
        tenant_id=1,
        project_id=1,
        request_id="req_1",
    )
    paused = service.pause(1, actor_id="1")
    resumed = service.resume(1, actor_id="1")
    draining = service.drain(1, actor_id="1")
    stopped = service.stop(1, actor_id="1")

    assert activated.desired_status == DeploymentDesiredStatus.active
    assert paused.desired_status == DeploymentDesiredStatus.paused
    assert resumed.desired_status == DeploymentDesiredStatus.active
    assert draining.desired_status == DeploymentDesiredStatus.draining
    assert stopped.desired_status == DeploymentDesiredStatus.stopped
    assert [entry.action for entry in service.audit_sink.entries] == [
        "deployment.activate",
        "deployment.pause",
        "deployment.resume",
        "deployment.drain",
        "deployment.stop",
    ]
    assert service.audit_sink.entries[0].tenant_id == 1
    assert service.audit_sink.entries[0].project_id == 1
    assert service.audit_sink.entries[0].request_id == "req_1"
    assert store.get(1).runtime_status == DeploymentRuntimeStatus.stopped


def test_deployment_control_rejects_scope_mismatch_before_policy() -> None:
    service, store = create_service()

    with pytest.raises(PolicyDeniedError, match="deployment_scope_mismatch"):
        service.activate(
            1,
            actor_id="1",
            tenant_id=2,
            project_id=1,
            request_id="req_scope",
        )

    assert store.get(1).desired_status == DeploymentDesiredStatus.draft
    assert service.audit_sink.entries[0].result == "denied"
    assert service.audit_sink.entries[0].tenant_id == 2
    assert service.audit_sink.entries[0].project_id == 1
    assert service.audit_sink.entries[0].request_id == "req_scope"
    assert service.audit_sink.entries[0].metadata["reason"] == "deployment_scope_mismatch"


def test_policy_denied_error_exposes_stable_error_code() -> None:
    service, _ = create_service()

    with pytest.raises(PolicyDeniedError) as exc_info:
        service.assert_accepts_new_run(
            1,
            tenant_id=2,
            project_id=1,
        )

    assert exc_info.value.reason == "deployment_scope_mismatch"
    assert exc_info.value.error_code == "deployment_scope_mismatch"


def test_restart_evicts_instances_without_changing_agent_version() -> None:
    service, _ = create_service()
    service.instances.register_loading(
        tenant_id=1,
        project_id=1,
        deployment_id=1,
        agent_id=1,
        agent_version_id=1,
        worker_id="worker_1",
        execution_profile_id="profile_1",
    )

    deployment = service.restart(1, actor_id="1")

    assert deployment.agent_version_id == 1
    assert deployment.desired_status == DeploymentDesiredStatus.active
    assert service.instances.list_by_deployment(1)[0].status == "evicted"


def test_reactivating_stopped_deployment_recomputes_runtime_status() -> None:
    service, store = create_service()

    service.stop(1, actor_id="1")
    activated = service.activate(1, actor_id="1")

    assert activated.desired_status == DeploymentDesiredStatus.active
    assert activated.runtime_status == DeploymentRuntimeStatus.not_loaded
    assert store.get(1).runtime_status == DeploymentRuntimeStatus.not_loaded


def test_policy_denial_blocks_control_action_and_writes_denied_audit() -> None:
    store = InMemoryDeploymentStore()
    store.add(
        DeploymentRecord(
            id=1,
            tenant_id=1,
            project_id=1,
            agent_id=1,
            agent_version_id=1,
            environment="prod",
        )
    )
    audit_sink = InMemoryAuditSink()
    service = DeploymentRuntimeControlService(
        deployments=store,
        policy_engine=StaticPolicyEngine(allowed=False, reason="maintenance_window"),
        audit_sink=audit_sink,
    )

    with pytest.raises(PolicyDeniedError):
        service.activate(
            1,
            actor_id="1",
            tenant_id=1,
            project_id=1,
            request_id="req_denied",
        )

    assert store.get(1).desired_status == DeploymentDesiredStatus.draft
    assert audit_sink.entries[0].result == "denied"
    assert audit_sink.entries[0].tenant_id == 1
    assert audit_sink.entries[0].project_id == 1
    assert audit_sink.entries[0].request_id == "req_denied"
    assert audit_sink.entries[0].metadata["reason"] == "maintenance_window"


@pytest.mark.asyncio
async def test_run_manager_rejects_new_runs_for_paused_deployment() -> None:
    service, _ = create_service()
    service.pause(1, actor_id="1")
    run_manager = RunManager(
        run_store=InMemoryRunStore(),
        task_backend=InMemoryTaskBackend(),
        deployment_gate=service,
    )

    with pytest.raises(PolicyDeniedError):
        await run_manager.create_run_task(
            tenant_id=1,
            project_id=1,
            agent_id=1,
            agent_version_id=1,
            deployment_id=1,
            input_data={"message": "hello"},
        )
