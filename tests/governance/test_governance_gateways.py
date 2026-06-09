from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from dimoo_run.catalog.service import CatalogItem, CatalogService
from dimoo_run.core.context import RuntimeContext
from dimoo_run.hitl.service import HumanTaskService
from dimoo_run.model_gateway.provider import (
    BudgetExceededError,
    InMemoryModelGatewayProvider,
    ModelGatewayConfig,
    ModelGatewayScopeMismatchError,
    ModelPolicyConfig,
    ModelPolicyDecisionError,
)
from dimoo_run.policy.decisions import Decision
from dimoo_run.policy.engine import InMemoryAuditSink, PolicyEngine, StaticPolicyRule
from dimoo_run.prompts.assets import AssetVersionError, PromptAssetStore
from dimoo_run.sandbox.policy import SandboxPolicy, SandboxPolicyViolation
from dimoo_run.secrets.provider import (
    InMemorySecretProvider,
    SecretAccessDeniedError,
    SecretScopeMismatchError,
)
from dimoo_run.tools.gateway import ToolDefinition, ToolGateway, ToolScopeMismatchError


def context() -> RuntimeContext:
    return RuntimeContext(
        tenant_id=1,
        project_id=1,
        run_id=1,
        task_id=1,
        agent_id=1,
        agent_version_id=1,
        deployment_id=1,
        user_id=1,
        thread_id="thread_1",
    )


def record_delete_call(
    executed: list[dict[str, Any]],
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def handler(payload: dict[str, Any]) -> dict[str, Any]:
        executed.append(payload)
        return {"deleted": True}

    return handler


def test_tool_gateway_requires_policy_and_creates_human_task_for_high_risk_tool() -> None:
    audit_sink = InMemoryAuditSink()
    hitl = HumanTaskService(
        audit_sink=audit_sink,
        now=lambda: datetime(2026, 5, 26, tzinfo=UTC),
    )
    engine = PolicyEngine(
        rules=[
            StaticPolicyRule(
                policy_id="destructive-tools-need-approval",
                resource_type="tool",
                action="call",
                risk_level="destructive",
                decision=Decision.require_approval,
                reason="approval_required",
            )
        ],
        audit_sink=InMemoryAuditSink(),
    )
    gateway = ToolGateway(policy_engine=engine, human_tasks=hitl)
    executed: list[dict[str, Any]] = []
    gateway.register(
        ToolDefinition(
            id="delete_records",
            tenant_id=1,
            project_id=1,
            name="delete_records",
            risk_level="destructive",
            schema={"type": "object"},
            handler=record_delete_call(executed),
        )
    )

    result = gateway.call(
        tool_id="delete_records",
        arguments={"ids": [1]},
        context=context(),
        actor_id="user_1",
    )

    assert result.status == "approval_required"
    assert result.human_task_id is not None
    assert executed == []
    assert hitl.tasks[result.human_task_id].type == "approval"
    assert any(record.resource_type == "human_task" for record in audit_sink.records)


def test_tool_gateway_rejects_cross_scope_tool_binding() -> None:
    gateway = ToolGateway(policy_engine=PolicyEngine(), human_tasks=HumanTaskService())
    gateway.register(
        ToolDefinition(
            id="cross_project_tool",
            tenant_id="tenant_2",
            project_id="project_2",
            name="cross_project_tool",
            risk_level="read",
            schema={"type": "object"},
            handler=record_delete_call([]),
        )
    )

    with pytest.raises(ToolScopeMismatchError):
        gateway.call(
            tool_id="cross_project_tool",
            arguments={},
            context=context(),
            actor_id="user_1",
        )


def test_secret_provider_checks_policy_and_never_returns_secret_in_audit() -> None:
    audit_sink = InMemoryAuditSink()
    engine = PolicyEngine(
        rules=[
            StaticPolicyRule(
                policy_id="deny-secret",
                resource_type="secret",
                action="read",
                decision=Decision.deny,
                reason="secret_access_denied",
            )
        ],
        audit_sink=audit_sink,
    )
    provider = InMemorySecretProvider(policy_engine=engine)
    provider.put_secret(
        tenant_id=1,
        project_id=1,
        name="OPENAI_API_KEY",
        value="sk-secret",
    )

    with pytest.raises(SecretAccessDeniedError):
        provider.get_secret(
            tenant_id=1,
            project_id=1,
            secret_name="OPENAI_API_KEY",
            context=context(),
        )

    assert audit_sink.records[0].metadata.get("secret_value") is None
    assert "sk-secret" not in str(audit_sink.records[0])


def test_secret_provider_records_allowed_secret_use_without_plaintext() -> None:
    audit_sink = InMemoryAuditSink()
    provider = InMemorySecretProvider(policy_engine=PolicyEngine(audit_sink=audit_sink))
    provider.put_secret(
        tenant_id=1,
        project_id=1,
        name="OPENAI_API_KEY",
        value="sk-secret",
    )

    secret = provider.get_secret(
        tenant_id=1,
        project_id=1,
        secret_name="OPENAI_API_KEY",
        context=context(),
    )

    assert secret == "sk-secret"
    assert audit_sink.records[0].result == "allow"
    assert audit_sink.records[0].resource_type == "secret"
    assert "sk-secret" not in str(audit_sink.records[0])


def test_secret_provider_rejects_context_scope_mismatch() -> None:
    provider = InMemorySecretProvider(policy_engine=PolicyEngine())
    provider.put_secret(
        tenant_id="tenant_2",
        project_id="project_2",
        name="OPENAI_API_KEY",
        value="sk-secret",
    )

    with pytest.raises(SecretScopeMismatchError):
        provider.get_secret(
            tenant_id="tenant_2",
            project_id="project_2",
            secret_name="OPENAI_API_KEY",
            context=context(),
        )


def test_model_gateway_enforces_budget_and_records_usage_snapshot() -> None:
    provider = InMemoryModelGatewayProvider(policy_engine=PolicyEngine())
    provider.register_gateway(
        ModelGatewayConfig(
            id="gateway_1",
            tenant_id=1,
            project_id=1,
            provider_type="newapi",
            base_url="https://newapi.example/v1",
            credential_ref="secret:newapi",
            default_model_group="default",
        )
    )
    provider.set_policy(
        ModelPolicyConfig(
            id="policy_1",
            tenant_id=1,
            project_id=1,
            gateway_id="gateway_1",
            default_model="gpt-4.1-mini",
            allowed_models={"gpt-4.1-mini"},
            max_cost_per_run=0.10,
            on_budget_exceeded="reject",
        )
    )

    request = provider.prepare_chat_request(
        context=context(),
        requested_model=None,
        estimated_cost=0.05,
    )
    snapshot = provider.record_usage(
        context=context(),
        gateway_request_id="gw_req_1",
        model="gpt-4.1-mini",
        prompt_tokens=10,
        completion_tokens=20,
        cost=0.03,
        currency="USD",
        raw_usage={"total_tokens": 30},
    )

    assert request.base_url == "https://newapi.example/v1"
    assert request.credential_ref == "secret:newapi"
    assert request.model == "gpt-4.1-mini"
    assert snapshot.run_id == 1
    assert snapshot.total_tokens == 30

    with pytest.raises(BudgetExceededError):
        provider.prepare_chat_request(
            context=context(),
            requested_model="gpt-4.1-mini",
            estimated_cost=0.20,
        )


def test_model_gateway_does_not_treat_approval_or_fallback_as_allow() -> None:
    provider = InMemoryModelGatewayProvider(
        policy_engine=PolicyEngine(
            rules=[
                StaticPolicyRule(
                    policy_id="approve-model",
                    resource_type="model_gateway",
                    action="use",
                    decision=Decision.require_approval,
                    reason="approval_required",
                )
            ]
        )
    )
    provider.register_gateway(
        ModelGatewayConfig(
            id="gateway_1",
            tenant_id=1,
            project_id=1,
            provider_type="newapi",
            base_url="https://newapi.example/v1",
            credential_ref="secret:newapi",
        )
    )
    provider.set_policy(
        ModelPolicyConfig(
            id="policy_1",
            tenant_id=1,
            project_id=1,
            gateway_id="gateway_1",
            default_model="gpt-4.1-mini",
            allowed_models={"gpt-4.1-mini"},
            max_cost_per_run=1,
            on_budget_exceeded="reject",
        )
    )

    with pytest.raises(ModelPolicyDecisionError) as exc_info:
        provider.prepare_chat_request(
            context=context(),
            requested_model=None,
            estimated_cost=0.05,
        )

    assert exc_info.value.decision == Decision.require_approval


def test_model_gateway_runtime_policy_uses_use_action_not_create() -> None:
    audit_sink = InMemoryAuditSink()
    provider = InMemoryModelGatewayProvider(
        policy_engine=PolicyEngine(
            rules=[
                StaticPolicyRule(
                    policy_id="deny-model-use",
                    resource_type="model_gateway",
                    action="use",
                    decision=Decision.deny,
                    reason="model_gateway_use_denied",
                )
            ],
            audit_sink=audit_sink,
        )
    )
    provider.register_gateway(
        ModelGatewayConfig(
            id="gateway_1",
            tenant_id=1,
            project_id=1,
            provider_type="newapi",
            base_url="https://newapi.example/v1",
            credential_ref="secret:newapi",
        )
    )
    provider.set_policy(
        ModelPolicyConfig(
            id="policy_1",
            tenant_id=1,
            project_id=1,
            gateway_id="gateway_1",
            default_model="gpt-4.1-mini",
            allowed_models={"gpt-4.1-mini"},
        )
    )

    with pytest.raises(PermissionError, match="model_gateway_use_denied"):
        provider.prepare_chat_request(
            context=context(),
            requested_model=None,
            estimated_cost=0.05,
        )

    assert audit_sink.records[0].resource_type == "model_gateway"
    assert audit_sink.records[0].action == "use"


def test_model_gateway_budget_require_approval_and_fallback_do_not_silently_allow() -> None:
    provider = InMemoryModelGatewayProvider(policy_engine=PolicyEngine())
    provider.register_gateway(
        ModelGatewayConfig(
            id="gateway_1",
            tenant_id=1,
            project_id=1,
            provider_type="newapi",
            base_url="https://newapi.example/v1",
            credential_ref="secret:newapi",
        )
    )
    provider.set_policy(
        ModelPolicyConfig(
            id="policy_1",
            tenant_id=1,
            project_id=1,
            gateway_id="gateway_1",
            default_model="gpt-4.1-mini",
            allowed_models={"gpt-4.1-mini"},
            max_cost_per_run=0.10,
            on_budget_exceeded="require_approval",
        )
    )

    with pytest.raises(ModelPolicyDecisionError) as exc_info:
        provider.prepare_chat_request(
            context=context(),
            requested_model=None,
            estimated_cost=0.20,
        )

    assert exc_info.value.decision == Decision.require_approval

    provider.set_policy(
        ModelPolicyConfig(
            id="policy_2",
            tenant_id=1,
            project_id=1,
            gateway_id="gateway_1",
            default_model="gpt-4.1-mini",
            allowed_models={"gpt-4.1-mini"},
            max_cost_per_run=0.10,
            on_budget_exceeded="fallback",
        )
    )
    with pytest.raises(ModelPolicyDecisionError) as fallback_error:
        provider.prepare_chat_request(
            context=context(),
            requested_model=None,
            estimated_cost=0.20,
        )
    assert fallback_error.value.decision == Decision.fallback


def test_model_gateway_rejects_cross_scope_gateway_binding() -> None:
    provider = InMemoryModelGatewayProvider(policy_engine=PolicyEngine())
    provider.register_gateway(
        ModelGatewayConfig(
            id="gateway_1",
            tenant_id="tenant_2",
            project_id="project_2",
            provider_type="newapi",
            base_url="https://newapi.example/v1",
            credential_ref="secret:newapi",
        )
    )
    provider.set_policy(
        ModelPolicyConfig(
            id="policy_1",
            tenant_id=1,
            project_id=1,
            gateway_id="gateway_1",
            default_model="gpt-4.1-mini",
            allowed_models={"gpt-4.1-mini"},
        )
    )

    with pytest.raises(ModelGatewayScopeMismatchError):
        provider.prepare_chat_request(
            context=context(),
            requested_model=None,
            estimated_cost=0.05,
        )


def test_catalog_prompt_assets_and_sandbox_policy_are_governed_boundaries() -> None:
    catalog = CatalogService(policy_engine=PolicyEngine())
    item = catalog.register(
        CatalogItem(
            id="tool_catalog_1",
            tenant_id=1,
            project_id=1,
            type="ToolCatalogItem",
            name="Search",
            provider="builtin",
            version="1.0.0",
            schema={"type": "object"},
            risk_level="read",
            required_permissions={"tool:call"},
        ),
        actor_id="user_1",
    )
    prompts = PromptAssetStore(policy_engine=PolicyEngine())
    prompt = prompts.create_prompt(
        tenant_id=1,
        project_id=1,
        name="support-system",
        version="1.0.0",
        content_ref="artifact://prompt/support/1.0.0",
        variables_schema={"type": "object"},
        created_by="user_1",
    )
    sandbox = SandboxPolicy(
        isolation_level="L2",
        network_policy="restricted",
        filesystem_policy="read_only",
        allowed_env={"DIMOORUN_RUN_ID"},
        allowed_secret_refs={"OPENAI_API_KEY"},
    )

    assert item.status == "active"
    assert prompt.version == "1.0.0"
    assert prompts.resolve_prompt(1, 1, "support-system", "1.0.0") == prompt
    with pytest.raises(AssetVersionError):
        prompts.resolve_prompt(1, 1, "support-system", "latest")
    with pytest.raises(SandboxPolicyViolation):
        sandbox.validate_env({"OPENAI_API_KEY": "leaked"})


def test_human_task_decision_is_audited_and_cannot_be_repeated() -> None:
    audit_sink = InMemoryAuditSink()
    hitl = HumanTaskService(audit_sink=audit_sink)
    task = hitl.create_approval(
        tenant_id=1,
        project_id=1,
        run_id=1,
        attempt_id=None,
        task_id=1,
        payload={"risk": "destructive"},
        requested_by="user_1",
    )

    decided = hitl.decide(task.id, actor_id="user_2", approved=True)

    assert decided.status == "approved"
    assert audit_sink.records[-1].resource_type == "human_task"
    assert audit_sink.records[-1].action == "decide"
    assert audit_sink.records[-1].result == "approved"
    with pytest.raises(PermissionError, match="human_task_not_pending"):
        hitl.decide(task.id, actor_id="user_3", approved=False)
# mypy: disable-error-code="arg-type"
