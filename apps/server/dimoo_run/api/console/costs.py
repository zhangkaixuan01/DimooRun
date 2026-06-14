from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from dimoo_run.api.console.common import (
    AuthorizationHeader,
    DeploymentControlDep,
    EnvironmentHeader,
    NativeRuntimeDep,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    console_read_actor,
)
from dimoo_run.api.dependencies import authenticate_api_key
from dimoo_run.core.config import Settings
from dimoo_run.costs import (
    BudgetPreviewInput,
    build_budget_preview,
    build_cost_anomalies,
    build_cost_attribution_summary,
)
from dimoo_run.domain.models import CostBudgetPolicy, CostSavedView, NotificationChannel
from dimoo_run.persistence.database import create_session_factory

CostGroupBy = Literal["agent", "deployment", "run", "provider", "model"]


class ConsoleCostBreakdownRead(BaseModel):
    class ConsoleCostQualityGateOverlayRead(BaseModel):
        status: str
        promotion_allowed: bool
        blocked_reason: str | None = None
        experiment_run_id: int | None = None
        average_score: float | None = None
        min_score: float | None = None
        candidate_agent_version_id: int | None = None

    group_by: CostGroupBy
    key: str
    label: str
    total_cost_usd: float
    total_tokens: int
    run_count: int
    failed_run_count: int
    latest_run_id: int | None = None
    latest_at: str | None = None
    quality_gate: ConsoleCostQualityGateOverlayRead | None = None


class ConsoleCostSummaryRead(BaseModel):
    window_days: int
    group_by: CostGroupBy
    total_cost_usd: float
    total_tokens: int
    run_count: int
    failed_run_count: int
    breakdown: list[ConsoleCostBreakdownRead] = Field(default_factory=list)


class ConsoleCostAnomalyRead(BaseModel):
    kind: str
    severity: str
    title: str
    summary: str
    cost_usd: float
    run_id: int | None = None
    deployment_id: int | None = None
    provider: str | None = None
    model: str | None = None


class ConsoleBudgetPreviewRequest(BaseModel):
    threshold_usd: float
    scope_type: Literal["tenant", "project", "environment", "agent", "deployment"]
    scope_ref: str | None = None
    reset_window: Literal["daily", "weekly", "monthly"] = "monthly"
    notification_channel: str
    action_mode: Literal["warn", "reject", "require_approval"] = "warn"


class ConsoleBudgetPreviewRead(BaseModel):
    scope_type: str
    scope_ref: str | None = None
    reset_window: str
    threshold_usd: float
    current_spend_usd: float
    projected_spend_usd: float
    utilization_ratio: float
    would_trigger: bool
    notification_preview: str
    action_preview: str
    top_contributors: list[ConsoleCostBreakdownRead] = Field(default_factory=list)


class ConsoleSavedCostViewRead(BaseModel):
    id: int
    name: str
    environment: str | None = None
    group_by: CostGroupBy
    window_days: int
    filters: dict[str, Any] = Field(default_factory=dict)
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class ConsoleSavedCostViewDetailRead(BaseModel):
    item: ConsoleSavedCostViewRead
    summary: ConsoleCostSummaryRead
    anomalies: list[ConsoleCostAnomalyRead] = Field(default_factory=list)


router = APIRouter(prefix="/v1/console/costs", tags=["console-costs"])


def _session_factory() -> sessionmaker[Session]:
    return create_session_factory(Settings.from_env().database.url)


@router.get("/summary", response_model=ConsoleCostSummaryRead)
def get_cost_summary(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    group_by: Annotated[CostGroupBy, Query()] = "deployment",
    window_days: Annotated[int, Query(ge=1, le=365)] = 30,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> ConsoleCostSummaryRead | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    _, tenant_id, project_id, environment = auth
    summary = build_cost_attribution_summary(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        group_by=group_by,
        window_days=window_days,
    )
    return ConsoleCostSummaryRead(
        window_days=summary.window_days,
        group_by=summary.group_by,
        total_cost_usd=summary.total_cost_usd,
        total_tokens=summary.total_tokens,
        run_count=summary.run_count,
        failed_run_count=summary.failed_run_count,
        breakdown=[_cost_breakdown_read(item) for item in summary.breakdown],
    )


@router.get("/anomalies", response_model=list[ConsoleCostAnomalyRead])
def get_cost_anomalies(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    window_days: Annotated[int, Query(ge=1, le=365)] = 30,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[ConsoleCostAnomalyRead] | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    _, tenant_id, project_id, environment = auth
    anomalies = build_cost_anomalies(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        window_days=window_days,
    )
    return [ConsoleCostAnomalyRead(**item.__dict__) for item in anomalies]


@router.post("/budgets/preview", response_model=ConsoleBudgetPreviewRead)
def preview_budget_policy(
    payload: ConsoleBudgetPreviewRequest,
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> ConsoleBudgetPreviewRead | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    actor, tenant_id, project_id, environment = auth
    denied = authenticate_api_key(
        authorization=authorization,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        required_scope="policy:update",
        request_id=x_request_id,
    )
    if isinstance(denied, JSONResponse):
        return denied
    _ = actor
    preview = build_budget_preview(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        preview=BudgetPreviewInput(**payload.model_dump()),
    )
    payload_data = dict(preview.__dict__)
    payload_data["top_contributors"] = [
        ConsoleCostBreakdownRead(**item.__dict__) for item in preview.top_contributors
    ]
    return ConsoleBudgetPreviewRead(**payload_data)


@router.get("/budgets/{policy_id}/preview", response_model=ConsoleBudgetPreviewRead)
def preview_saved_budget_policy(
    policy_id: int,
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> ConsoleBudgetPreviewRead | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    _, tenant_id, project_id, environment = auth
    denied = authenticate_api_key(
        authorization=authorization,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        required_scope="policy:update",
        request_id=x_request_id,
    )
    if isinstance(denied, JSONResponse):
        return denied
    with _session_factory()() as session:
        policy = session.get(CostBudgetPolicy, policy_id)
        if (
            policy is None
            or policy.is_deleted
            or policy.tenant_id != tenant_id
            or policy.project_id not in {None, project_id}
            or (policy.environment is not None and policy.environment != environment)
        ):
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "cost_budget_policy_not_found",
                    "message": "Cost budget policy was not found in the requested scope.",
                    "request_id": x_request_id,
                },
            )
        channel = session.get(NotificationChannel, policy.channel_id)
        notification_channel = (
            str(channel.target_ref)
            if channel is not None and not channel.is_deleted
            else f"channel:{policy.channel_id}"
        )
        preview_environment = policy.environment or environment
    preview = build_budget_preview(
        runtime=runtime,
        deployments=deployments,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=preview_environment,
        preview=BudgetPreviewInput(
            threshold_usd=policy.threshold_usd,
            scope_type=policy.scope_type,  # type: ignore[arg-type]
            scope_ref=policy.scope_ref,
            reset_window=policy.reset_window,  # type: ignore[arg-type]
            notification_channel=notification_channel,
            action_mode=policy.action_mode,  # type: ignore[arg-type]
        ),
    )
    payload_data = dict(preview.__dict__)
    payload_data["top_contributors"] = [
        ConsoleCostBreakdownRead(**item.__dict__) for item in preview.top_contributors
    ]
    return ConsoleBudgetPreviewRead(**payload_data)


@router.get("/views/{view_id}", response_model=ConsoleSavedCostViewDetailRead)
def get_saved_cost_view(
    view_id: int,
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> ConsoleSavedCostViewDetailRead | JSONResponse:
    auth = console_read_actor(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    _, tenant_id, project_id, environment = auth
    with _session_factory()() as session:
        view = session.get(CostSavedView, view_id)
        if (
            view is None
            or view.is_deleted
            or view.tenant_id != tenant_id
            or view.project_id not in {None, project_id}
            or (view.environment is not None and view.environment != environment)
        ):
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "cost_saved_view_not_found",
                    "message": "Cost saved view was not found in the requested scope.",
                    "request_id": x_request_id,
                },
            )
        effective_environment = view.environment or environment
        summary = build_cost_attribution_summary(
            runtime=runtime,
            deployments=deployments,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=effective_environment,
            group_by=view.group_by,  # type: ignore[arg-type]
            window_days=view.window_days,
        )
        anomalies = build_cost_anomalies(
            runtime=runtime,
            deployments=deployments,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=effective_environment,
            window_days=view.window_days,
        )
        return ConsoleSavedCostViewDetailRead(
            item=_saved_view_read(view),
            summary=ConsoleCostSummaryRead(
                window_days=summary.window_days,
                group_by=summary.group_by,
                total_cost_usd=summary.total_cost_usd,
                total_tokens=summary.total_tokens,
                run_count=summary.run_count,
                failed_run_count=summary.failed_run_count,
                breakdown=[_cost_breakdown_read(item) for item in summary.breakdown],
            ),
            anomalies=[ConsoleCostAnomalyRead(**item.__dict__) for item in anomalies],
        )


def _cost_breakdown_read(item: Any) -> ConsoleCostBreakdownRead:
    payload = dict(item.__dict__)
    quality_gate = payload.get("quality_gate")
    if quality_gate is not None:
        payload["quality_gate"] = (
            ConsoleCostBreakdownRead.ConsoleCostQualityGateOverlayRead(
                **quality_gate.__dict__
            )
        )
    return ConsoleCostBreakdownRead(**payload)


def _saved_view_read(view: CostSavedView) -> ConsoleSavedCostViewRead:
    return ConsoleSavedCostViewRead(
        id=view.id,
        name=view.name,
        environment=view.environment,
        group_by=view.group_by,  # type: ignore[arg-type]
        window_days=view.window_days,
        filters=dict(view.filters_json or {}),
        status=view.status,
        metadata=dict(view.metadata_json or {}),
        created_at=view.created_at.isoformat() if view.created_at is not None else None,
        updated_at=view.updated_at.isoformat() if view.updated_at is not None else None,
    )
