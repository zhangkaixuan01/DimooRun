from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from dimoo_run.domain.enums import DeploymentDesiredStatus
from dimoo_run.observability.audit import InMemoryComplianceAuditLog
from dimoo_run.sandbox.policy import SandboxPolicy


class ContainerPoolBoundaryError(RuntimeError):
    error_code = "container_pool_boundary_violation"


@dataclass(frozen=True)
class ContainerPoolRequest:
    tenant_id: int
    project_id: int
    deployment_id: int
    desired_status: str
    env: dict[str, str] = field(default_factory=dict)
    secret_refs: set[str] = field(default_factory=set)
    resources: dict[str, str] = field(default_factory=dict)


class ContainerPool:
    def __init__(self, *, policy: SandboxPolicy, audit_log: InMemoryComplianceAuditLog) -> None:
        self.policy = policy
        self.audit_log = audit_log
        self.executions: list[dict[str, Any]] = []

    def run(
        self,
        request: ContainerPoolRequest,
        *,
        actor_id: str | None,
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            if request.desired_status != DeploymentDesiredStatus.active.value:
                raise ContainerPoolBoundaryError("deployment_not_active")
            self.policy.validate_env(request.env)
            for secret_ref in request.secret_refs:
                self.policy.validate_secret_ref(secret_ref)
            result = operation()
        except Exception as exc:
            self.audit_log.record(
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                actor_id=actor_id,
                actor_type="service_account" if actor_id else "system",
                action="sandbox.execute",
                resource_type="deployment",
                resource_id=request.deployment_id,
                result="deny",
                metadata={"reason": str(exc), "resources": request.resources},
            )
            raise
        self.audit_log.record(
            tenant_id=request.tenant_id,
            project_id=request.project_id,
            actor_id=actor_id,
            actor_type="service_account" if actor_id else "system",
            action="sandbox.execute",
            resource_type="deployment",
            resource_id=request.deployment_id,
            result="allow",
            metadata={"resources": request.resources},
        )
        self.executions.append({"deployment_id": request.deployment_id, "result": result})
        return result
