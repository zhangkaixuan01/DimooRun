from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from dimoo_run.core.context import RuntimeContext
from dimoo_run.policy.decisions import Decision
from dimoo_run.policy.engine import AuditRecord, PolicyEngine, PolicyRequest


class SecretAccessDeniedError(PermissionError):
    error_code = "secret_access_denied"


class SecretScopeMismatchError(PermissionError):
    error_code = "secret_scope_mismatch"


@dataclass
class SecretRecord:
    tenant_id: str
    project_id: str | None
    name: str
    value: str
    status: str = "active"
    last_used_at: datetime | None = None


class InMemorySecretProvider:
    def __init__(
        self,
        *,
        policy_engine: PolicyEngine,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.policy_engine = policy_engine
        self._now = now or (lambda: datetime.now(UTC))
        self.secrets: dict[tuple[str, str | None, str], SecretRecord] = {}

    def put_secret(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        name: str,
        value: str,
    ) -> SecretRecord:
        record = SecretRecord(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            value=value,
        )
        self.secrets[(tenant_id, project_id, name)] = record
        return record

    def get_secret(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        secret_name: str,
        context: RuntimeContext,
    ) -> str:
        if tenant_id != context.tenant_id or project_id != context.project_id:
            self.policy_engine.record_violation(
                PolicyRequest(
                    tenant_id=context.tenant_id,
                    project_id=context.project_id,
                    actor_id=context.user_id or context.service_account_id,
                    actor_type="service_account" if context.service_account_id else "user",
                    resource_type="secret",
                    resource_id=secret_name,
                    action="read",
                    runtime_context=context.to_metadata(),
                ),
                reason="secret_scope_mismatch",
                metadata={"requested_tenant_id": tenant_id, "requested_project_id": project_id},
            )
            raise SecretScopeMismatchError(secret_name)
        record = self.secrets[(tenant_id, project_id, secret_name)]
        decision = self.policy_engine.evaluate(
            PolicyRequest(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=context.user_id or context.service_account_id,
                actor_type="service_account" if context.service_account_id else "user",
                resource_type="secret",
                resource_id=secret_name,
                action="read",
                agent_id=context.agent_id,
                agent_version_id=context.agent_version_id,
                deployment_id=context.deployment_id,
                runtime_context=context.to_metadata(),
                request_metadata={"secret_name": secret_name},
            )
        )
        if decision.decision == Decision.deny:
            raise SecretAccessDeniedError(decision.reason or "secret_access_denied")
        record.last_used_at = self._now()
        self.policy_engine.audit_sink.write(
            AuditRecord(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=context.user_id or context.service_account_id,
                actor_type="service_account" if context.service_account_id else "user",
                resource_type="secret",
                resource_id=secret_name,
                action="read",
                result="allow",
                metadata={"secret_name": secret_name},
            )
        )
        return record.value
