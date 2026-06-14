from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from dimoo_run.api.native.runtime import NativeRuntimeStore, SQLAlchemyNativeRuntimeStore
from dimoo_run.costs.budget_policy import BudgetPreviewInput, build_budget_preview
from dimoo_run.deployments.service import DeploymentRuntimeControlService
from dimoo_run.domain.models import CostBudgetPolicy, NotificationChannel


@dataclass(frozen=True)
class CostBudgetPolicyHit:
    policy_id: int
    name: str
    action_mode: str
    scope_type: str
    scope_ref: str | None
    environment: str | None
    threshold_usd: float
    current_spend_usd: float
    channel_id: int
    channel_name: str
    notification_channel: str


@dataclass(frozen=True)
class CostBudgetEnforcementDecision:
    blocking_policy: CostBudgetPolicyHit | None
    warning_policies: list[CostBudgetPolicyHit]


def evaluate_persisted_budget_policies(
    *,
    session: Session | None,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    tenant_id: int,
    project_id: int,
    environment: str,
    agent_id: int,
    deployment_id: int,
) -> CostBudgetEnforcementDecision:
    if session is None:
        return CostBudgetEnforcementDecision(blocking_policy=None, warning_policies=[])

    policies = list(
        session.scalars(
            _policy_statement(
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
                agent_id=agent_id,
                deployment_id=deployment_id,
            )
        )
    )
    if not policies:
        return CostBudgetEnforcementDecision(blocking_policy=None, warning_policies=[])

    notifications = {
        channel.id: channel
        for channel in session.scalars(
            select(NotificationChannel).where(
                NotificationChannel.tenant_id == tenant_id,
                NotificationChannel.project_id == project_id,
                NotificationChannel.is_deleted.is_(False),
            )
        )
    }
    blocking_policy: CostBudgetPolicyHit | None = None
    warning_policies: list[CostBudgetPolicyHit] = []
    for policy in policies:
        channel = notifications.get(policy.channel_id)
        notification_channel = (
            str(channel.target_ref)
            if channel is not None and channel.status == "active"
            else f"channel:{policy.channel_id}"
        )
        preview = build_budget_preview(
            runtime=runtime,
            deployments=deployments,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=policy.environment or environment,
            preview=BudgetPreviewInput(
                threshold_usd=policy.threshold_usd,
                scope_type=policy.scope_type,  # type: ignore[arg-type]
                scope_ref=policy.scope_ref,
                reset_window=policy.reset_window,  # type: ignore[arg-type]
                notification_channel=notification_channel,
                action_mode=policy.action_mode,  # type: ignore[arg-type]
            ),
        )
        if not preview.would_trigger:
            continue
        hit = CostBudgetPolicyHit(
            policy_id=policy.id,
            name=policy.name,
            action_mode=policy.action_mode,
            scope_type=policy.scope_type,
            scope_ref=policy.scope_ref,
            environment=policy.environment,
            threshold_usd=policy.threshold_usd,
            current_spend_usd=preview.current_spend_usd,
            channel_id=policy.channel_id,
            channel_name=(
                str(channel.target_ref)
                if channel is not None and channel.status == "active"
                else f"channel:{policy.channel_id}"
            ),
            notification_channel=notification_channel,
        )
        if policy.action_mode == "warn":
            warning_policies.append(hit)
            continue
        if blocking_policy is None:
            blocking_policy = hit
    return CostBudgetEnforcementDecision(
        blocking_policy=blocking_policy,
        warning_policies=warning_policies,
    )


def _policy_statement(
    *,
    tenant_id: int,
    project_id: int,
    environment: str,
    agent_id: int,
    deployment_id: int,
) -> Select[tuple[CostBudgetPolicy]]:
    return (
        select(CostBudgetPolicy)
        .where(
            CostBudgetPolicy.tenant_id == tenant_id,
            CostBudgetPolicy.is_deleted.is_(False),
            CostBudgetPolicy.status == "active",
            CostBudgetPolicy.project_id.in_([project_id, None]),
            CostBudgetPolicy.environment.in_([environment, None]),
        )
        .where(
            ((CostBudgetPolicy.scope_type == "tenant") & CostBudgetPolicy.scope_ref.is_(None))
            | (
                (CostBudgetPolicy.scope_type == "project")
                & CostBudgetPolicy.scope_ref.in_([None, str(project_id)])
            )
            | (
                (CostBudgetPolicy.scope_type == "environment")
                & CostBudgetPolicy.scope_ref.in_([None, environment])
            )
            | (
                (CostBudgetPolicy.scope_type == "agent")
                & (CostBudgetPolicy.scope_ref == str(agent_id))
            )
            | (
                (CostBudgetPolicy.scope_type == "deployment")
                & (CostBudgetPolicy.scope_ref == str(deployment_id))
            )
        )
        .order_by(CostBudgetPolicy.id.asc())
    )
