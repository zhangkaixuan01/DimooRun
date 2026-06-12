import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.core.context import RuntimeContext
from dimoo_run.domain.models import (
    ModelGateway,
    ModelPolicy,
)
from dimoo_run.domain.models import (
    ModelUsageSnapshot as ModelUsageSnapshotModel,
)
from dimoo_run.policy.decisions import Decision
from dimoo_run.policy.engine import AuditRecord, PolicyEngine, PolicyRequest


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


class ModelGatewayTimeoutError(TimeoutError):
    error_code = "model_gateway_timeout"


@dataclass(frozen=True)
class ModelGatewayConfig:
    id: int
    tenant_id: int
    project_id: int | None
    provider_type: Literal["newapi", "litellm", "openai_compatible", "custom"]
    base_url: str
    credential_ref: str
    default_model_group: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelPolicyConfig:
    id: int
    tenant_id: int
    project_id: int | None
    gateway_id: int
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
    gateway_id: int
    base_url: str
    credential_ref: str
    model: str
    provider_type: str


@dataclass(frozen=True)
class ModelUsageSnapshot:
    id: int
    run_id: int
    attempt_id: int | None
    gateway_id: int
    gateway_request_id: str | None
    model: str
    provider: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    currency: str
    raw_usage: dict[str, Any]


@dataclass(frozen=True)
class ModelExecutionResult:
    request: PreparedModelRequest
    payload: dict[str, Any]
    usage_snapshot: ModelUsageSnapshot


class InMemoryModelGatewayProvider:
    def __init__(self, *, policy_engine: PolicyEngine) -> None:
        self.policy_engine = policy_engine
        self.gateways: dict[int, ModelGatewayConfig] = {}
        self.policies: dict[tuple[int, int | None], ModelPolicyConfig] = {}
        self.usage_snapshots: list[ModelUsageSnapshot] = []
        self._next_usage_id = 0

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
        actor_id = (
            str(context.user_id or context.service_account_id)
            if context.user_id is not None or context.service_account_id is not None
            else None
        )
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
                actor_id=actor_id,
                actor_type="service_account" if context.service_account_id else "user",
                resource_type="model_gateway",
                resource_id=gateway.id,
                action="use",
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
            id=self._allocate_usage_id(),
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
        actor_id = (
            str(context.user_id or context.service_account_id)
            if context.user_id is not None or context.service_account_id is not None
            else None
        )
        if gateway.tenant_id != context.tenant_id or gateway.project_id != context.project_id:
            self.policy_engine.record_violation(
                PolicyRequest(
                    tenant_id=context.tenant_id,
                    project_id=context.project_id,
                    actor_id=actor_id,
                    actor_type="service_account" if context.service_account_id else "user",
                    resource_type="model_gateway",
                    resource_id=gateway.id,
                    action="use",
                    runtime_context=context.to_metadata(),
                ),
                reason="model_gateway_scope_mismatch",
                metadata={
                    "gateway_tenant_id": gateway.tenant_id,
                    "gateway_project_id": gateway.project_id,
                },
            )
            raise ModelGatewayScopeMismatchError(gateway.id)

    def _allocate_usage_id(self) -> int:
        self._next_usage_id += 1
        return self._next_usage_id


class SQLAlchemyModelGatewayProvider:
    def __init__(self, *, session: Session, policy_engine: PolicyEngine) -> None:
        self.session = session
        self.policy_engine = policy_engine

    def prepare_chat_request(
        self,
        *,
        context: RuntimeContext,
        requested_model: str | None,
        estimated_cost: float,
    ) -> PreparedModelRequest:
        actor_id = (
            str(context.user_id or context.service_account_id)
            if context.user_id is not None or context.service_account_id is not None
            else None
        )
        gateway = self._gateway(context)
        policy = self._policy(context, gateway_id=gateway.id)
        model = requested_model or policy.default_model
        if policy.allowed_models_json and model not in set(policy.allowed_models_json):
            raise ModelNotAllowedError(model)
        if model in set(policy.denied_models_json):
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
        self._assert_gateway_scope(gateway, context)
        decision = self.policy_engine.evaluate(
            PolicyRequest(
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                actor_id=actor_id,
                actor_type="service_account" if context.service_account_id else "user",
                resource_type="model_gateway",
                resource_id=gateway.id,
                action="use",
                agent_id=context.agent_id,
                agent_version_id=context.agent_version_id,
                deployment_id=context.deployment_id,
                environment=context.environment,
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
        gateway = self._gateway(context)
        self._assert_gateway_scope(gateway, context)
        snapshot = ModelUsageSnapshotModel(
            tenant_id=context.tenant_id,
            project_id=context.project_id,
            run_id=context.run_id,
            attempt_id=context.attempt_id,
            gateway_id=gateway.id,
            gateway_request_id=gateway_request_id,
            model=model,
            provider=gateway.provider_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            currency=currency,
            raw_usage_json=raw_usage,
        )
        self.session.add(snapshot)
        self.session.flush()
        return ModelUsageSnapshot(
            id=snapshot.id,
            run_id=snapshot.run_id,
            attempt_id=snapshot.attempt_id,
            gateway_id=snapshot.gateway_id,
            gateway_request_id=snapshot.gateway_request_id,
            model=snapshot.model,
            provider=snapshot.provider,
            prompt_tokens=snapshot.prompt_tokens,
            completion_tokens=snapshot.completion_tokens,
            total_tokens=snapshot.total_tokens,
            cost=snapshot.cost,
            currency=snapshot.currency,
            raw_usage=snapshot.raw_usage_json,
        )

    async def run_chat(
        self,
        *,
        context: RuntimeContext,
        requested_model: str | None,
        estimated_cost: float,
        execute: Callable[[PreparedModelRequest], Awaitable[dict[str, Any]] | dict[str, Any]],
        timeout_seconds: float | None = None,
    ) -> ModelExecutionResult:
        request = self.prepare_chat_request(
            context=context,
            requested_model=requested_model,
            estimated_cost=estimated_cost,
        )
        try:
            payload = await _invoke_model_call(
                execute,
                request,
                timeout_seconds=timeout_seconds,
            )
        except TimeoutError as exc:
            self.policy_engine.audit_sink.write(
                AuditRecord(
                    tenant_id=context.tenant_id,
                    project_id=context.project_id,
                    actor_id=str(context.user_id or context.service_account_id)
                    if context.user_id is not None or context.service_account_id is not None
                    else None,
                    actor_type="service_account" if context.service_account_id else "user",
                    resource_type="model_gateway",
                    resource_id=request.gateway_id,
                    action="use",
                    result="timeout",
                    metadata={"model": request.model},
                )
            )
            raise ModelGatewayTimeoutError("model_gateway_timeout") from exc
        usage = payload.get("usage")
        usage_data = usage if isinstance(usage, dict) else {}
        snapshot = self.record_usage(
            context=context,
            gateway_request_id=_string_or_none(payload.get("gateway_request_id")),
            model=_string_or_none(payload.get("model")) or request.model,
            prompt_tokens=_int_value(usage_data.get("prompt_tokens")),
            completion_tokens=_int_value(usage_data.get("completion_tokens")),
            cost=_float_value(usage_data.get("cost")),
            currency=_string_or_none(usage_data.get("currency")) or "USD",
            raw_usage=usage_data,
        )
        self.policy_engine.audit_sink.write(
            AuditRecord(
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                actor_id=str(context.user_id or context.service_account_id)
                if context.user_id is not None or context.service_account_id is not None
                else None,
                actor_type="service_account" if context.service_account_id else "user",
                resource_type="model_gateway",
                resource_id=request.gateway_id,
                action="use",
                result="allow",
                metadata={
                    "model": snapshot.model,
                    "gateway_request_id": snapshot.gateway_request_id,
                    "total_tokens": snapshot.total_tokens,
                    "cost": snapshot.cost,
                    "currency": snapshot.currency,
                },
            )
        )
        return ModelExecutionResult(request=request, payload=payload, usage_snapshot=snapshot)

    def _gateway(self, context: RuntimeContext) -> ModelGateway:
        gateway_config = context.config.get("model_gateway")
        gateway_id = gateway_config.get("id") if isinstance(gateway_config, dict) else None
        if not isinstance(gateway_id, int):
            raise KeyError("model_gateway_not_configured")
        gateway = self.session.get(ModelGateway, gateway_id)
        if gateway is None or gateway.is_deleted or gateway.status != "active":
            raise KeyError("model_gateway_not_found")
        return gateway

    def _policy(self, context: RuntimeContext, *, gateway_id: int) -> ModelPolicy:
        statement = (
            select(ModelPolicy)
            .where(
                ModelPolicy.tenant_id == context.tenant_id,
                ModelPolicy.project_id == context.project_id,
                ModelPolicy.gateway_id == gateway_id,
                ModelPolicy.status == "active",
                ModelPolicy.is_deleted.is_(False),
            )
            .order_by(ModelPolicy.id.asc())
        )
        policies = list(self.session.scalars(statement))
        for policy in policies:
            if policy.agent_id is not None and policy.agent_id != context.agent_id:
                continue
            if (
                policy.agent_version_id is not None
                and policy.agent_version_id != context.agent_version_id
            ):
                continue
            return policy
        raise KeyError("model_policy_not_found")

    def _assert_gateway_scope(
        self,
        gateway: ModelGateway,
        context: RuntimeContext,
    ) -> None:
        actor_id = (
            str(context.user_id or context.service_account_id)
            if context.user_id is not None or context.service_account_id is not None
            else None
        )
        if gateway.tenant_id != context.tenant_id or gateway.project_id != context.project_id:
            self.policy_engine.record_violation(
                PolicyRequest(
                    tenant_id=context.tenant_id,
                    project_id=context.project_id,
                    actor_id=actor_id,
                    actor_type="service_account" if context.service_account_id else "user",
                    resource_type="model_gateway",
                    resource_id=gateway.id,
                    action="use",
                    runtime_context=context.to_metadata(),
                ),
                reason="model_gateway_scope_mismatch",
                metadata={
                    "gateway_tenant_id": gateway.tenant_id,
                    "gateway_project_id": gateway.project_id,
                },
            )
            raise ModelGatewayScopeMismatchError(gateway.id)


async def _invoke_model_call(
    execute: Callable[[PreparedModelRequest], Awaitable[dict[str, Any]] | dict[str, Any]],
    request: PreparedModelRequest,
    *,
    timeout_seconds: float | None,
) -> dict[str, Any]:
    async def _call() -> dict[str, Any]:
        value = execute(request)
        if inspect.isawaitable(value):
            resolved = await value
        else:
            resolved = value
        return resolved if isinstance(resolved, dict) else {"output": resolved}

    if timeout_seconds is None:
        return await _call()
    return await asyncio.wait_for(_call(), timeout=timeout_seconds)


def _int_value(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _float_value(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None
