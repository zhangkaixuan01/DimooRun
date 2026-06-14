from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from dimoo_run.api.native.runtime import NativeRuntimeStore, SQLAlchemyNativeRuntimeStore
from dimoo_run.costs.attribution import (
    CostAttributionBreakdownView,
    CostGroupBy,
    build_cost_attribution_summary,
)
from dimoo_run.deployments.service import DeploymentRuntimeControlService

BudgetScope = Literal["tenant", "project", "environment", "agent", "deployment"]
BudgetResetWindow = Literal["daily", "weekly", "monthly"]
BudgetActionMode = Literal["warn", "reject", "require_approval"]


@dataclass(frozen=True)
class BudgetPreviewInput:
    threshold_usd: float
    scope_type: BudgetScope
    scope_ref: str | None
    reset_window: BudgetResetWindow
    notification_channel: str
    action_mode: BudgetActionMode


@dataclass(frozen=True)
class BudgetPreviewResult:
    scope_type: BudgetScope
    scope_ref: str | None
    reset_window: BudgetResetWindow
    threshold_usd: float
    current_spend_usd: float
    projected_spend_usd: float
    utilization_ratio: float
    would_trigger: bool
    notification_preview: str
    action_preview: str
    top_contributors: list[CostAttributionBreakdownView]


def build_budget_preview(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    tenant_id: int,
    project_id: int,
    environment: str,
    preview: BudgetPreviewInput,
    now: datetime | None = None,
) -> BudgetPreviewResult:
    window_days = {"daily": 1, "weekly": 7, "monthly": 30}[preview.reset_window]
    summary = build_cost_attribution_summary(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        window_days=window_days,
        group_by=_group_by_for_scope(preview.scope_type),
        now=now or datetime.now(UTC),
    )
    filtered = _filter_breakdown(
        summary.breakdown,
        scope_type=preview.scope_type,
        scope_ref=preview.scope_ref,
    )
    current_spend = round(sum(item.total_cost_usd for item in filtered), 6)
    ratio = current_spend / preview.threshold_usd if preview.threshold_usd > 0 else 0.0
    projected = round(current_spend * (30 / window_days), 6)
    return BudgetPreviewResult(
        scope_type=preview.scope_type,
        scope_ref=preview.scope_ref,
        reset_window=preview.reset_window,
        threshold_usd=preview.threshold_usd,
        current_spend_usd=current_spend,
        projected_spend_usd=projected,
        utilization_ratio=ratio,
        would_trigger=current_spend >= preview.threshold_usd,
        notification_preview=(
            f"Notify {preview.notification_channel} when {preview.scope_type} reaches "
            f"{ratio * 100:.1f}% of ${preview.threshold_usd:.2f}."
        ),
        action_preview=(
            f"When exceeded, DimooRun will {preview.action_mode.replace('_', ' ')} "
            f"new spend for {preview.scope_type}."
        ),
        top_contributors=filtered[:5],
    )


def _group_by_for_scope(scope_type: BudgetScope) -> CostGroupBy:
    if scope_type == "deployment":
        return "deployment"
    if scope_type == "agent":
        return "agent"
    return "deployment"


def _filter_breakdown(
    breakdown: list[CostAttributionBreakdownView],
    *,
    scope_type: BudgetScope,
    scope_ref: str | None,
) -> list[CostAttributionBreakdownView]:
    if scope_type in {"tenant", "project", "environment"} or scope_ref is None:
        return breakdown
    return [item for item in breakdown if item.key == scope_ref]
