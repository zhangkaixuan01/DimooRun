from dataclasses import dataclass, field
from typing import Protocol

from dimoo_run.deployments.instances import AgentInstanceRecord, AgentInstanceRegistry
from dimoo_run.deployments.status import RuntimeStatusSummary, aggregate_runtime_status
from dimoo_run.domain.enums import DeploymentDesiredStatus, DeploymentRuntimeStatus


class DeploymentNotFoundError(KeyError):
    pass


class PolicyDeniedError(PermissionError):
    def __init__(self, reason: str, *, error_code: str = "policy_denied") -> None:
        self.reason = reason
        self.error_code = error_code
        super().__init__(reason)


@dataclass
class DeploymentRecord:
    id: int
    tenant_id: int
    project_id: int
    agent_id: int
    agent_version_id: int
    environment: str
    desired_status: DeploymentDesiredStatus = DeploymentDesiredStatus.draft
    runtime_status: DeploymentRuntimeStatus = DeploymentRuntimeStatus.not_loaded
    replicas: int = 1
    config_json: dict[str, object] = field(default_factory=dict)
    last_runtime_error: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None


class DeploymentPolicyEngine(Protocol):
    def evaluate(
        self,
        *,
        actor_id: str | None,
        action: str,
        deployment: DeploymentRecord,
    ) -> PolicyDecision:
        ...


class AllowAllPolicyEngine:
    def evaluate(
        self,
        *,
        actor_id: str | None,
        action: str,
        deployment: DeploymentRecord,
    ) -> PolicyDecision:
        _ = actor_id, action, deployment
        return PolicyDecision(allowed=True)


class StaticPolicyEngine:
    def __init__(self, *, allowed: bool, reason: str | None = None) -> None:
        self.allowed = allowed
        self.reason = reason

    def evaluate(
        self,
        *,
        actor_id: str | None,
        action: str,
        deployment: DeploymentRecord,
    ) -> PolicyDecision:
        _ = actor_id, action, deployment
        return PolicyDecision(allowed=self.allowed, reason=self.reason)


@dataclass(frozen=True)
class AuditEntry:
    action: str
    resource_type: str
    resource_id: int
    actor_id: str | None
    tenant_id: int | None
    project_id: int | None
    request_id: str | None
    result: str
    metadata: dict[str, str] = field(default_factory=dict)


class InMemoryAuditSink:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def write(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


class InMemoryDeploymentStore:
    def __init__(self) -> None:
        self.deployments: dict[int, DeploymentRecord] = {}
        self._next_id = 1

    def add(self, deployment: DeploymentRecord) -> DeploymentRecord:
        if deployment.id <= 0:
            deployment.id = self._next_id
            self._next_id += 1
        else:
            self._next_id = max(self._next_id, deployment.id + 1)
        self.deployments[deployment.id] = deployment
        return deployment

    def get(self, deployment_id: int) -> DeploymentRecord:
        try:
            return self.deployments[deployment_id]
        except KeyError as exc:
            raise DeploymentNotFoundError(deployment_id) from exc

    def list(
        self,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
    ) -> list[DeploymentRecord]:
        deployments = list(self.deployments.values())
        if tenant_id is not None:
            deployments = [
                deployment for deployment in deployments if deployment.tenant_id == tenant_id
            ]
        if project_id is not None:
            deployments = [
                deployment for deployment in deployments if deployment.project_id == project_id
            ]
        return deployments

    def save(self, deployment: DeploymentRecord) -> DeploymentRecord:
        self.deployments[deployment.id] = deployment
        return deployment


class DeploymentRuntimeControlService:
    def __init__(
        self,
        *,
        deployments: InMemoryDeploymentStore | None = None,
        instances: AgentInstanceRegistry | None = None,
        policy_engine: DeploymentPolicyEngine | None = None,
        audit_sink: InMemoryAuditSink | None = None,
    ) -> None:
        self.deployments = deployments or InMemoryDeploymentStore()
        self.instances = instances or AgentInstanceRegistry()
        self.policy_engine = policy_engine or AllowAllPolicyEngine()
        self.audit_sink = audit_sink or InMemoryAuditSink()

    def activate(
        self,
        deployment_id: int,
        *,
        actor_id: str | None = None,
        tenant_id: int | None = None,
        project_id: int | None = None,
        request_id: str | None = None,
    ) -> DeploymentRecord:
        return self._control(
            deployment_id,
            actor_id=actor_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=request_id,
            action="activate",
            desired_status=DeploymentDesiredStatus.active,
        )

    def pause(
        self,
        deployment_id: int,
        *,
        actor_id: str | None = None,
        tenant_id: int | None = None,
        project_id: int | None = None,
        request_id: str | None = None,
    ) -> DeploymentRecord:
        return self._control(
            deployment_id,
            actor_id=actor_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=request_id,
            action="pause",
            desired_status=DeploymentDesiredStatus.paused,
        )

    def resume(
        self,
        deployment_id: int,
        *,
        actor_id: str | None = None,
        tenant_id: int | None = None,
        project_id: int | None = None,
        request_id: str | None = None,
    ) -> DeploymentRecord:
        return self._control(
            deployment_id,
            actor_id=actor_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=request_id,
            action="resume",
            desired_status=DeploymentDesiredStatus.active,
        )

    def drain(
        self,
        deployment_id: int,
        *,
        actor_id: str | None = None,
        tenant_id: int | None = None,
        project_id: int | None = None,
        request_id: str | None = None,
    ) -> DeploymentRecord:
        deployment = self._control(
            deployment_id,
            actor_id=actor_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=request_id,
            action="drain",
            desired_status=DeploymentDesiredStatus.draining,
        )
        for instance in self.instances.list_by_deployment(deployment_id):
            if instance.status != "evicted":
                instance.status = "draining"
        return deployment

    def stop(
        self,
        deployment_id: int,
        *,
        actor_id: str | None = None,
        tenant_id: int | None = None,
        project_id: int | None = None,
        request_id: str | None = None,
    ) -> DeploymentRecord:
        deployment = self._control(
            deployment_id,
            actor_id=actor_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=request_id,
            action="stop",
            desired_status=DeploymentDesiredStatus.stopped,
        )
        self.instances.evict_deployment(deployment_id, reason="stop")
        deployment.runtime_status = DeploymentRuntimeStatus.stopped
        return deployment

    def restart(
        self,
        deployment_id: int,
        *,
        actor_id: str | None = None,
        tenant_id: int | None = None,
        project_id: int | None = None,
        request_id: str | None = None,
    ) -> DeploymentRecord:
        self._control(
            deployment_id,
            actor_id=actor_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=request_id,
            action="restart",
            desired_status=DeploymentDesiredStatus.active,
        )
        self.instances.evict_deployment(deployment_id, reason="restart")
        self.summarize(deployment_id)
        return DeploymentRecord(**self.deployments.get(deployment_id).__dict__)

    def list_instances(self, deployment_id: int) -> list[AgentInstanceRecord]:
        self.deployments.get(deployment_id)
        return self.instances.list_by_deployment(deployment_id)

    def summarize(
        self,
        deployment_id: int,
        *,
        running_runs: int = 0,
        queue_backlog: int = 0,
    ) -> RuntimeStatusSummary:
        deployment = self.deployments.get(deployment_id)
        summary = aggregate_runtime_status(
            desired_status=deployment.desired_status,
            instances=self.instances.list_by_deployment(deployment_id),
            running_runs=running_runs,
            queue_backlog=queue_backlog,
        )
        deployment.runtime_status = summary.runtime_status
        deployment.last_runtime_error = summary.last_runtime_error
        return summary

    def assert_accepts_new_run(
        self,
        deployment_id: int,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        agent_id: int | None = None,
        agent_version_id: int | None = None,
    ) -> None:
        deployment = self.deployments.get(deployment_id)
        self._assert_deployment_binding(
            deployment,
            tenant_id=tenant_id,
            project_id=project_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
        )
        if deployment.desired_status != DeploymentDesiredStatus.active:
            raise PolicyDeniedError(
                "Deployment "
                f"{deployment_id} does not accept new runs while "
                f"{deployment.desired_status}.",
                error_code="deployment_not_accepting_runs",
            )

    def _control(
        self,
        deployment_id: int,
        *,
        actor_id: str | None,
        tenant_id: int | None,
        project_id: int | None,
        request_id: str | None,
        action: str,
        desired_status: DeploymentDesiredStatus,
    ) -> DeploymentRecord:
        deployment = self.deployments.get(deployment_id)
        try:
            self._assert_deployment_binding(
                deployment,
                tenant_id=tenant_id,
                project_id=project_id,
            )
        except PolicyDeniedError as exc:
            self._write_audit(
                action=f"deployment.{action}",
                deployment=deployment,
                actor_id=actor_id,
                tenant_id=tenant_id,
                project_id=project_id,
                request_id=request_id,
                result="denied",
                metadata={"reason": exc.reason},
            )
            raise
        decision = self.policy_engine.evaluate(
            actor_id=actor_id,
            action=f"deployment.{action}",
            deployment=deployment,
        )
        if not decision.allowed:
            self._write_audit(
                action=f"deployment.{action}",
                deployment=deployment,
                actor_id=actor_id,
                tenant_id=tenant_id,
                project_id=project_id,
                request_id=request_id,
                result="denied",
                metadata={"reason": decision.reason or "policy_denied"},
            )
            raise PolicyDeniedError(decision.reason or "policy_denied")

        deployment.desired_status = desired_status
        if desired_status == DeploymentDesiredStatus.stopped:
            deployment.runtime_status = DeploymentRuntimeStatus.stopped
        elif desired_status == DeploymentDesiredStatus.draining:
            deployment.runtime_status = DeploymentRuntimeStatus.draining
        else:
            deployment.runtime_status = aggregate_runtime_status(
                desired_status=deployment.desired_status,
                instances=self.instances.list_by_deployment(deployment_id),
                running_runs=0,
                queue_backlog=0,
            ).runtime_status
        if hasattr(self.deployments, "save"):
            self.deployments.save(deployment)
        self._write_audit(
            action=f"deployment.{action}",
            deployment=deployment,
            actor_id=actor_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=request_id,
            result="allowed",
        )
        return DeploymentRecord(**deployment.__dict__)

    def _assert_deployment_binding(
        self,
        deployment: DeploymentRecord,
        *,
        tenant_id: int | None,
        project_id: int | None,
        agent_id: int | None = None,
        agent_version_id: int | None = None,
    ) -> None:
        if tenant_id is not None and deployment.tenant_id != tenant_id:
            raise PolicyDeniedError(
                "deployment_scope_mismatch",
                error_code="deployment_scope_mismatch",
            )
        if project_id is not None and deployment.project_id != project_id:
            raise PolicyDeniedError(
                "deployment_scope_mismatch",
                error_code="deployment_scope_mismatch",
            )
        if agent_id is not None and deployment.agent_id != agent_id:
            raise PolicyDeniedError(
                "deployment_agent_version_mismatch",
                error_code="deployment_agent_version_mismatch",
            )
        if agent_version_id is not None and deployment.agent_version_id != agent_version_id:
            raise PolicyDeniedError(
                "deployment_agent_version_mismatch",
                error_code="deployment_agent_version_mismatch",
            )

    def _write_audit(
        self,
        *,
        action: str,
        deployment: DeploymentRecord,
        actor_id: str | None,
        tenant_id: int | None,
        project_id: int | None,
        request_id: str | None,
        result: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.audit_sink.write(
            AuditEntry(
                action=action,
                resource_type="deployment",
                resource_id=deployment.id,
                actor_id=actor_id,
                tenant_id=tenant_id or deployment.tenant_id,
                project_id=project_id or deployment.project_id,
                request_id=request_id,
                result=result,
                metadata=metadata or {},
            )
        )
