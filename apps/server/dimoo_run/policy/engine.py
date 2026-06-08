from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from dimoo_run.policy.decisions import Decision, PolicyDecision


@dataclass(frozen=True)
class PolicyRequest:
    tenant_id: int
    project_id: int | None
    actor_id: str | None
    actor_type: str
    resource_type: str
    resource_id: int | None
    action: str
    risk_level: str | None = None
    user_id: int | None = None
    service_account_id: int | None = None
    agent_id: int | None = None
    agent_version_id: int | None = None
    deployment_id: int | None = None
    environment: str | None = None
    runtime_context: dict[str, Any] = field(default_factory=dict)
    request_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditRecord:
    tenant_id: int
    project_id: int | None
    actor_id: str | None
    actor_type: str
    resource_type: str
    resource_id: int | None
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
    tenant_id: int | None = None
    project_id: int | None = None
    environment: str | None = None
    risk_level: str | None = None
    resource_id: int | None = None
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
            limits=_metadata_limits(self.metadata),
            redactions=tuple(_metadata_redactions(self.metadata)),
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
        matches = [rule for rule in self.rules if rule.matches(request)]
        for rule in matches:
            if rule.decision == Decision.deny:
                decision = rule.to_decision()
                self._audit_when_required(request, decision)
                return decision
        for rule in matches:
            if rule.decision == Decision.require_approval:
                decision = rule.to_decision()
                self._audit_when_required(request, decision)
                return decision
        if matches:
            return _compose_allow_decision(matches)
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


def _compose_allow_decision(rules: list[StaticPolicyRule]) -> PolicyDecision:
    matched_policy_ids: list[str] = []
    limits: dict[str, Any] = {}
    redactions: list[str] = []
    primary_rule = rules[0]
    for rule in rules:
        if rule.decision not in {
            Decision.allow,
            Decision.allow_with_redaction,
            Decision.allow_with_limit,
        }:
            continue
        matched_policy_ids.append(rule.policy_id)
        limits.update(_metadata_limits(rule.metadata))
        for redaction in _metadata_redactions(rule.metadata):
            if redaction not in redactions:
                redactions.append(redaction)
        if (
            primary_rule.decision != Decision.allow_with_limit
            and rule.decision == Decision.allow_with_limit
        ):
            primary_rule = rule
        elif (
            primary_rule.decision == Decision.allow
            and rule.decision == Decision.allow_with_redaction
        ):
            primary_rule = rule
    if limits:
        decision = Decision.allow_with_limit
    elif redactions:
        decision = Decision.allow_with_redaction
    else:
        decision = primary_rule.decision
    return PolicyDecision(
        decision=decision,
        reason=primary_rule.reason,
        matched_policy_ids=tuple(matched_policy_ids),
        limits=limits,
        redactions=tuple(redactions),
        expires_at=primary_rule.expires_at,
        metadata={
            "limits": limits,
            "redactions": redactions,
        },
    )


def _metadata_limits(metadata: dict[str, Any]) -> dict[str, Any]:
    value = metadata.get("limits")
    return dict(value) if isinstance(value, dict) else {}


def _metadata_redactions(metadata: dict[str, Any]) -> list[str]:
    value = metadata.get("redactions")
    if not isinstance(value, list | tuple):
        return []
    return [item for item in (str(item).strip() for item in value) if item]
