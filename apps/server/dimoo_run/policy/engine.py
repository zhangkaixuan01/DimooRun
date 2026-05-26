from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from dimoo_run.policy.decisions import Decision, PolicyDecision


@dataclass(frozen=True)
class PolicyRequest:
    tenant_id: str
    project_id: str | None
    actor_id: str | None
    actor_type: str
    resource_type: str
    resource_id: str | None
    action: str
    risk_level: str | None = None
    user_id: str | None = None
    service_account_id: str | None = None
    agent_id: str | None = None
    agent_version_id: str | None = None
    deployment_id: str | None = None
    environment: str | None = None
    runtime_context: dict[str, Any] = field(default_factory=dict)
    request_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditRecord:
    tenant_id: str
    project_id: str | None
    actor_id: str | None
    actor_type: str
    resource_type: str
    resource_id: str | None
    action: str
    result: str
    reason: str | None = None
    matched_policy_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditSink(Protocol):
    def write(self, record: AuditRecord) -> None: ...


class InMemoryAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def write(self, record: AuditRecord) -> None:
        self.records.append(record)


@dataclass(frozen=True)
class StaticPolicyRule:
    policy_id: str
    resource_type: str
    action: str
    decision: Decision
    reason: str
    tenant_id: str | None = None
    project_id: str | None = None
    environment: str | None = None
    risk_level: str | None = None
    resource_id: str | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches(self, request: PolicyRequest) -> bool:
        if self.resource_type != request.resource_type or self.action != request.action:
            return False
        if self.tenant_id is not None and self.tenant_id != request.tenant_id:
            return False
        if self.project_id is not None and self.project_id != request.project_id:
            return False
        if self.environment is not None and self.environment != request.environment:
            return False
        if self.risk_level is not None and self.risk_level != request.risk_level:
            return False
        if self.resource_id is not None and self.resource_id != request.resource_id:
            return False
        return True

    def to_decision(self) -> PolicyDecision:
        if self.decision == Decision.deny:
            return PolicyDecision.deny(reason=self.reason, policy_id=self.policy_id)
        if self.decision == Decision.require_approval:
            return PolicyDecision.require_approval(reason=self.reason, policy_id=self.policy_id)
        return PolicyDecision(
            decision=self.decision,
            reason=self.reason,
            matched_policy_ids=(self.policy_id,),
            expires_at=self.expires_at,
            metadata=self.metadata,
        )


class PolicyEngine:
    def __init__(
        self,
        *,
        rules: list[StaticPolicyRule] | None = None,
        audit_sink: AuditSink | None = None,
    ) -> None:
        self.rules = rules or []
        self.audit_sink = audit_sink or InMemoryAuditSink()

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        for rule in self.rules:
            if rule.matches(request):
                decision = rule.to_decision()
                self._audit_when_required(request, decision)
                return decision
        return PolicyDecision.allow()

    def assert_allowed(self, request: PolicyRequest) -> PolicyDecision:
        decision = self.evaluate(request)
        if decision.decision == Decision.deny:
            raise PermissionError(decision.reason or "policy_denied")
        return decision

    def record_violation(
        self,
        request: PolicyRequest,
        *,
        reason: str = "policy_violation",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.audit_sink.write(
            AuditRecord(
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                actor_id=request.actor_id,
                actor_type=request.actor_type,
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                action=request.action,
                result="policy_violation",
                reason=reason,
                metadata=metadata or {},
            )
        )

    def _audit_when_required(self, request: PolicyRequest, decision: PolicyDecision) -> None:
        if decision.decision not in {Decision.deny, Decision.require_approval}:
            return
        self.audit_sink.write(
            AuditRecord(
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                actor_id=request.actor_id,
                actor_type=request.actor_type,
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                action=request.action,
                result=decision.decision.value,
                reason=decision.reason,
                matched_policy_ids=decision.matched_policy_ids,
                metadata=decision.metadata,
            )
        )
