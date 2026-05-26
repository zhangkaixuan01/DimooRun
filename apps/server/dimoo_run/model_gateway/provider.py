from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from dimoo_run.core.context import RuntimeContext
from dimoo_run.policy.decisions import Decision
from dimoo_run.policy.engine import PolicyEngine, PolicyRequest


class BudgetExceededError(PermissionError):
    error_code = "model_budget_exceeded"


class ModelNotAllowedError(PermissionError):
    error_code = "model_not_allowed"


class ModelPolicyDecisionError(PermissionError):
    def __init__(self, decision: Decision, reason: str | None = None) -> None:
        self.decision = decision
        self.reason = reason
        super().__init__(reason or decision.value)


class ModelGatewayScopeMismatchError(PermissionError):
    error_code = "model_gateway_scope_mismatch"


@dataclass(frozen=True)
class ModelGatewayConfig:
    id: str
    tenant_id: str
    project_id: str | None
    provider_type: Literal["newapi", "litellm", "openai_compatible", "custom"]
    base_url: str
    credential_ref: str
    default_model_group: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelPolicyConfig:
    id: str
    tenant_id: str
    project_id: str | None
    gateway_id: str
    default_model: str
    allowed_models: set[str] = field(default_factory=set)
    denied_models: set[str] = field(default_factory=set)
    max_tokens_per_run: int | None = None
    max_cost_per_run: float | None = None
    max_cost_per_day: float | None = None
    fallback_policy: dict[str, Any] = field(default_factory=dict)
    on_budget_exceeded: Literal["reject", "warn", "require_approval", "fallback"] = "reject"


@dataclass(frozen=True)
class PreparedModelRequest:
    gateway_id: str
    base_url: str
    credential_ref: str
    model: str
    provider_type: str


@dataclass(frozen=True)
class ModelUsageSnapshot:
    id: str
    run_id: str
    attempt_id: str | None
    gateway_id: str
    gateway_request_id: str | None
    model: str
    provider: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    currency: str
    raw_usage: dict[str, Any]


class InMemoryModelGatewayProvider:
    def __init__(self, *, policy_engine: PolicyEngine) -> None:
        self.policy_engine = policy_engine
        self.gateways: dict[str, ModelGatewayConfig] = {}
        self.policies: dict[tuple[str, str | None], ModelPolicyConfig] = {}
        self.usage_snapshots: list[ModelUsageSnapshot] = []

    def register_gateway(self, gateway: ModelGatewayConfig) -> ModelGatewayConfig:
        self.gateways[gateway.id] = gateway
        return gateway

    def set_policy(self, policy: ModelPolicyConfig) -> ModelPolicyConfig:
        self.policies[(policy.tenant_id, policy.project_id)] = policy
        return policy

    def prepare_chat_request(
        self,
        *,
        context: RuntimeContext,
        requested_model: str | None,
        estimated_cost: float,
    ) -> PreparedModelRequest:
        policy = self.policies[(context.tenant_id, context.project_id)]
        model = requested_model or policy.default_model
        if policy.allowed_models and model not in policy.allowed_models:
            raise ModelNotAllowedError(model)
        if model in policy.denied_models:
            raise ModelNotAllowedError(model)
        if policy.max_cost_per_run is not None and estimated_cost > policy.max_cost_per_run:
            if policy.on_budget_exceeded == "reject":
                raise BudgetExceededError("max_cost_per_run")
            if policy.on_budget_exceeded == "require_approval":
                raise ModelPolicyDecisionError(
                    Decision.require_approval,
                    "model_budget_requires_approval",
                )
            if policy.on_budget_exceeded == "fallback":
                raise ModelPolicyDecisionError(Decision.fallback, "model_budget_requires_fallback")
        gateway = self.gateways[policy.gateway_id]
        self._assert_gateway_scope(gateway, context)
        decision = self.policy_engine.evaluate(
            PolicyRequest(
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                actor_id=context.user_id or context.service_account_id,
                actor_type="service_account" if context.service_account_id else "user",
                resource_type="model_gateway",
                resource_id=gateway.id,
                action="create",
                agent_id=context.agent_id,
                agent_version_id=context.agent_version_id,
                deployment_id=context.deployment_id,
                runtime_context=context.to_metadata(),
                request_metadata={"model": model, "estimated_cost": estimated_cost},
            )
        )
        if decision.decision == Decision.deny:
            raise PermissionError(decision.reason or "model_gateway_denied")
        if decision.decision not in {Decision.allow, Decision.allow_with_limit}:
            raise ModelPolicyDecisionError(decision.decision, decision.reason)
        return PreparedModelRequest(
            gateway_id=gateway.id,
            base_url=gateway.base_url,
            credential_ref=gateway.credential_ref,
            model=model,
            provider_type=gateway.provider_type,
        )

    def record_usage(
        self,
        *,
        context: RuntimeContext,
        gateway_request_id: str | None,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        currency: str,
        raw_usage: dict[str, Any],
    ) -> ModelUsageSnapshot:
        policy = self.policies[(context.tenant_id, context.project_id)]
        gateway = self.gateways[policy.gateway_id]
        self._assert_gateway_scope(gateway, context)
        snapshot = ModelUsageSnapshot(
            id=str(uuid4()),
            run_id=context.run_id,
            attempt_id=None,
            gateway_id=policy.gateway_id,
            gateway_request_id=gateway_request_id,
            model=model,
            provider=gateway.provider_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            currency=currency,
            raw_usage=raw_usage,
        )
        self.usage_snapshots.append(snapshot)
        return snapshot

    def _assert_gateway_scope(
        self,
        gateway: ModelGatewayConfig,
        context: RuntimeContext,
    ) -> None:
        if gateway.tenant_id != context.tenant_id or gateway.project_id != context.project_id:
            self.policy_engine.record_violation(
                PolicyRequest(
                    tenant_id=context.tenant_id,
                    project_id=context.project_id,
                    actor_id=context.user_id or context.service_account_id,
                    actor_type="service_account" if context.service_account_id else "user",
                    resource_type="model_gateway",
                    resource_id=gateway.id,
                    action="create",
                    runtime_context=context.to_metadata(),
                ),
                reason="model_gateway_scope_mismatch",
                metadata={
                    "gateway_tenant_id": gateway.tenant_id,
                    "gateway_project_id": gateway.project_id,
                },
            )
            raise ModelGatewayScopeMismatchError(gateway.id)
