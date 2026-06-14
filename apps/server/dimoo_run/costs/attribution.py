from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select

from dimoo_run.api.native.runtime import NativeRuntimeStore, SQLAlchemyNativeRuntimeStore
from dimoo_run.deployments.service import DeploymentRuntimeControlService
from dimoo_run.domain.models import ModelUsageSnapshot as ModelUsageSnapshotModel

CostGroupBy = Literal["agent", "deployment", "run", "provider", "model"]


@dataclass(frozen=True)
class CostUsageRow:
    run_id: int
    agent_id: int
    deployment_id: int | None
    environment: str | None
    provider: str | None
    model: str | None
    cost_usd: float
    total_tokens: int
    status: str
    created_at: datetime


@dataclass(frozen=True)
class CostQualityGateOverlayView:
    status: str
    promotion_allowed: bool
    blocked_reason: str | None
    experiment_run_id: int | None
    average_score: float | None
    min_score: float | None
    candidate_agent_version_id: int | None


@dataclass(frozen=True)
class CostAttributionBreakdownView:
    group_by: CostGroupBy
    key: str
    label: str
    total_cost_usd: float
    total_tokens: int
    run_count: int
    failed_run_count: int
    latest_run_id: int | None
    latest_at: str | None
    quality_gate: CostQualityGateOverlayView | None = None


@dataclass(frozen=True)
class CostAttributionSummaryView:
    window_days: int
    group_by: CostGroupBy
    total_cost_usd: float
    total_tokens: int
    run_count: int
    failed_run_count: int
    breakdown: list[CostAttributionBreakdownView]


@dataclass(frozen=True)
class CostAnomalyView:
    kind: str
    severity: str
    title: str
    summary: str
    cost_usd: float
    run_id: int | None = None
    deployment_id: int | None = None
    provider: str | None = None
    model: str | None = None


def build_cost_attribution_summary(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    tenant_id: int,
    project_id: int,
    environment: str,
    window_days: int = 30,
    group_by: CostGroupBy = "deployment",
    now: datetime | None = None,
) -> CostAttributionSummaryView:
    scoped_deployments = {
        deployment.id: deployment
        for deployment in deployments.deployments.list(
            tenant_id=tenant_id,
            project_id=project_id,
        )
        if deployment.environment == environment
    }
    rows = _load_cost_rows(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        window_days=window_days,
        now=now,
    )
    grouped: dict[str, list[CostUsageRow]] = defaultdict(list)
    labels: dict[str, str] = {}
    for row in rows:
        key, label = _group_key(group_by=group_by, row=row)
        grouped[key].append(row)
        labels[key] = label
    breakdown = [
        CostAttributionBreakdownView(
            group_by=group_by,
            key=key,
            label=labels[key],
            total_cost_usd=round(sum(item.cost_usd for item in items), 6),
            total_tokens=sum(item.total_tokens for item in items),
            run_count=len({item.run_id for item in items}),
            failed_run_count=len({item.run_id for item in items if item.status == "failed"}),
            latest_run_id=max(items, key=lambda item: item.created_at).run_id if items else None,
            latest_at=max(items, key=lambda item: item.created_at).created_at.isoformat()
            if items
            else None,
            quality_gate=(
                _deployment_quality_gate_overlay(
                    scoped_deployments.get(int(key)) if key.isdigit() else None
                )
                if group_by == "deployment"
                else None
            ),
        )
        for key, items in sorted(
            grouped.items(),
            key=lambda item: sum(row.cost_usd for row in item[1]),
            reverse=True,
        )
    ]
    return CostAttributionSummaryView(
        window_days=window_days,
        group_by=group_by,
        total_cost_usd=round(sum(item.cost_usd for item in rows), 6),
        total_tokens=sum(item.total_tokens for item in rows),
        run_count=len({item.run_id for item in rows}),
        failed_run_count=len({item.run_id for item in rows if item.status == "failed"}),
        breakdown=breakdown,
    )


def build_cost_anomalies(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    tenant_id: int,
    project_id: int,
    environment: str,
    window_days: int = 30,
    now: datetime | None = None,
) -> list[CostAnomalyView]:
    rows = _load_cost_rows(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        window_days=window_days,
        now=now,
    )
    if not rows:
        return []
    anomalies: list[CostAnomalyView] = []
    per_run: dict[int, list[CostUsageRow]] = defaultdict(list)
    for row in rows:
        per_run[row.run_id].append(row)
    total_run_cost = sum(sum(item.cost_usd for item in items) for items in per_run.values())
    average_run_cost = total_run_cost / max(len(per_run), 1)
    for run_id, items in sorted(per_run.items()):
        run_cost = sum(item.cost_usd for item in items)
        run_tokens = sum(item.total_tokens for item in items)
        status = items[0].status
        if status == "failed" and run_cost > 0:
            anomalies.append(
                CostAnomalyView(
                    kind="high_cost_failed_run",
                    severity="warning" if run_cost < 1 else "danger",
                    title=f"Failed run {run_id} consumed billable usage",
                    summary=f"Run failed after spending ${run_cost:.2f} and {run_tokens} tokens.",
                    cost_usd=round(run_cost, 6),
                    run_id=run_id,
                    deployment_id=items[0].deployment_id,
                    provider=items[0].provider,
                    model=items[0].model,
                )
            )
        spike_threshold = max(average_run_cost * 2, 0.05)
        if len(per_run) == 1:
            spike_threshold = min(spike_threshold, 0.5)
        if run_cost > spike_threshold:
            anomalies.append(
                CostAnomalyView(
                    kind="cost_spike",
                    severity="danger" if run_cost > max(average_run_cost * 4, 0.5) else "warning",
                    title=f"Run {run_id} cost spike",
                    summary=(
                        f"Run cost ${run_cost:.2f} exceeds the current average "
                        f"run cost baseline ${average_run_cost:.2f}."
                    ),
                    cost_usd=round(run_cost, 6),
                    run_id=run_id,
                    deployment_id=items[0].deployment_id,
                    provider=items[0].provider,
                    model=items[0].model,
                )
            )
    per_provider: dict[str, list[CostUsageRow]] = defaultdict(list)
    for row in rows:
        per_provider[row.provider or "unknown"].append(row)
    for provider, items in per_provider.items():
        failed_cost = sum(item.cost_usd for item in items if item.status == "failed")
        total_cost = sum(item.cost_usd for item in items)
        if total_cost > 0 and failed_cost / total_cost >= 0.5 and failed_cost > 0:
            anomalies.append(
                CostAnomalyView(
                    kind="provider_error_cost_correlation",
                    severity="warning",
                    title=f"Provider {provider} is consuming spend on failed runs",
                    summary=(
                        f"${failed_cost:.2f} of ${total_cost:.2f} for provider {provider} "
                        "came from failed runs."
                    ),
                    cost_usd=round(failed_cost, 6),
                    provider=provider,
                )
            )
    return anomalies[:20]


def _load_cost_rows(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    tenant_id: int,
    project_id: int,
    environment: str,
    window_days: int,
    now: datetime | None,
) -> list[CostUsageRow]:
    current = now or datetime.now(UTC)
    window_start = current - timedelta(days=window_days)
    scoped_deployments = {
        deployment.id: deployment
        for deployment in deployments.deployments.list(tenant_id=tenant_id, project_id=project_id)
        if deployment.environment == environment
    }
    runs = [
        run
        for run in runtime.list_runs(tenant_id=tenant_id, project_id=project_id)
        if _coerce_utc(run.created_at) >= window_start
        and (run.deployment_id is None or run.deployment_id in scoped_deployments)
    ]
    run_map = {run.id: run for run in runs}
    if isinstance(runtime, SQLAlchemyNativeRuntimeStore):
        snapshots = list(
            runtime.session.scalars(
                select(ModelUsageSnapshotModel).where(
                    ModelUsageSnapshotModel.tenant_id == tenant_id,
                    ModelUsageSnapshotModel.project_id == project_id,
                    ModelUsageSnapshotModel.created_at >= window_start,
                    ModelUsageSnapshotModel.run_id.in_(list(run_map.keys()) or [-1]),
                )
            )
        )
        rows = [
            CostUsageRow(
                run_id=snapshot.run_id,
                agent_id=run_map[snapshot.run_id].agent_id,
                deployment_id=run_map[snapshot.run_id].deployment_id,
                environment=(
                    scoped_deployments[deployment_id].environment
                    if (deployment_id := run_map[snapshot.run_id].deployment_id) is not None
                    and deployment_id in scoped_deployments
                    else None
                ),
                provider=snapshot.provider,
                model=snapshot.model,
                cost_usd=float(snapshot.cost),
                total_tokens=int(snapshot.total_tokens),
                status=run_map[snapshot.run_id].status.value,
                created_at=snapshot.created_at,
            )
            for snapshot in snapshots
            if snapshot.run_id in run_map
        ]
    else:
        rows = []
        for run in runs:
            if not isinstance(run.output, dict):
                continue
            cost = _float_value(run.output.get("cost"))
            total_tokens = _int_value(run.output.get("total_tokens"))
            if cost <= 0 and total_tokens <= 0:
                continue
            rows.append(
                CostUsageRow(
                    run_id=run.id,
                    agent_id=run.agent_id,
                    deployment_id=run.deployment_id,
                    environment=(
                        scoped_deployments[run.deployment_id].environment
                        if run.deployment_id is not None and run.deployment_id in scoped_deployments
                        else None
                    ),
                    provider=_string_value(run.output.get("provider")),
                    model=_string_value(run.output.get("model")),
                    cost_usd=cost,
                    total_tokens=total_tokens,
                    status=run.status.value,
                    created_at=run.created_at,
                )
            )
    return rows


def _group_key(*, group_by: CostGroupBy, row: CostUsageRow) -> tuple[str, str]:
    if group_by == "agent":
        key = str(row.agent_id)
        return key, f"Agent #{row.agent_id}"
    if group_by == "deployment":
        key = str(row.deployment_id or "unbound")
        label = f"Deployment #{row.deployment_id}" if row.deployment_id is not None else "Unbound"
        return key, label
    if group_by == "run":
        key = str(row.run_id)
        return key, f"Run #{row.run_id}"
    if group_by == "provider":
        key = row.provider or "unknown"
        return key, key
    key = row.model or "unknown"
    return key, key


def _deployment_quality_gate_overlay(
    deployment: object | None,
) -> CostQualityGateOverlayView | None:
    if deployment is None or not hasattr(deployment, "config_json"):
        return None
    config = getattr(deployment, "config_json", None)
    if not isinstance(config, dict):
        return None
    promotion = config.get("promotion")
    if not isinstance(promotion, dict):
        return None
    quality_gate = promotion.get("quality_gate")
    if not isinstance(quality_gate, dict):
        return None
    evidence = quality_gate.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    experiment_run_id = promotion.get("experiment_run_id", evidence.get("experiment_run_id"))
    return CostQualityGateOverlayView(
        status=str(quality_gate.get("status") or "unknown"),
        promotion_allowed=bool(quality_gate.get("promotion_allowed")),
        blocked_reason=(
            str(quality_gate["blocked_reason"])
            if quality_gate.get("blocked_reason") is not None
            else None
        ),
        experiment_run_id=int(experiment_run_id) if isinstance(experiment_run_id, int) else None,
        average_score=_float_value(evidence.get("average_score"))
        if evidence.get("average_score") is not None
        else None,
        min_score=_float_value(evidence.get("min_score"))
        if evidence.get("min_score") is not None
        else None,
        candidate_agent_version_id=(
            int(evidence["candidate_agent_version_id"])
            if isinstance(evidence.get("candidate_agent_version_id"), int)
            else None
        ),
    )


def _float_value(value: object) -> float:
    try:
        if isinstance(value, bool):
            return 0.0
        if not isinstance(value, (int, float, str)):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int_value(value: object) -> int:
    try:
        if isinstance(value, bool):
            return 0
        if not isinstance(value, (int, float, str)):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _string_value(value: object) -> str | None:
    return str(value) if isinstance(value, str) and value else None


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
