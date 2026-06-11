from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from dimoo_run.api.dependencies import (
    AuthorizationHeader,
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    authenticate_api_key,
    error_response,
)
from dimoo_run.api.native.dependencies import get_native_runtime
from dimoo_run.api.native.deployments import default_deployment_control
from dimoo_run.api.native.runtime import NativeRuntimeStore, SQLAlchemyNativeRuntimeStore
from dimoo_run.deployments.service import DeploymentRuntimeControlService
from dimoo_run.domain.enums import RunStatus, TaskStatus
from dimoo_run.domain.models import IncidentEvent
from dimoo_run.observability.otel import redact_event_payload, render_prometheus_metrics
from dimoo_run.runtime.capacity import build_worker_health_views, default_worker_registry

router = APIRouter(tags=["runtime-observability"])
NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]


class RuntimeMetricsSummaryRead(BaseModel):
    run_count_today: int
    success_rate: float
    p95_latency_ms: int
    p99_latency_ms: int
    queue_backlog: int
    running_tasks: int
    worker_ready: int
    worker_total: int
    dead_letters: int
    retries: int
    active_incidents: int
    active_workers: int
    failed_runs: int
    monthly_cost_usd: float
    pending_approvals: int


class RuntimeQueueMetricsRead(BaseModel):
    queue: str
    queue_backlog: int
    running_tasks: int
    leased_tasks: int
    retrying_tasks: int
    dead_letters: int
    oldest_task_age_seconds: float | None = None


class RuntimeWorkerMetricsRead(BaseModel):
    worker_id: str
    heartbeat_age_seconds: float | None = None
    readiness: str
    liveness: str
    active_attempts: int
    retrying_tasks: int
    dead_letter_tasks: int


class RuntimeTrendPointRead(BaseModel):
    label: str
    runs: int
    success_rate: float


class RuntimeIncidentRead(BaseModel):
    run_id: int
    status: str
    error_summary: str
    created_at: str


class RuntimeMetricsSnapshotRead(BaseModel):
    summary: RuntimeMetricsSummaryRead
    queues: list[RuntimeQueueMetricsRead] = Field(default_factory=list)
    workers: list[RuntimeWorkerMetricsRead] = Field(default_factory=list)
    active_incidents: list[RuntimeIncidentRead] = Field(default_factory=list)
    trend_points: list[RuntimeTrendPointRead] = Field(default_factory=list)


class RuntimeEventQueryRead(BaseModel):
    run_id: int
    event_id: str
    sequence: int
    type: str
    visibility_level: str
    trace_id: str | None = None
    request_id: str | None = None
    payload: dict[str, Any]


def _auth(
    *,
    authorization: str | None,
    tenant_id: int | None,
    project_id: int | None,
    environment: str | None,
    request_id: str | None,
) -> tuple[int, int, str] | JSONResponse:
    if tenant_id is None or project_id is None or environment is None:
        return error_response(
            status_code=400,
            error_code="request_scope_required",
            message="X-Tenant-Id, X-Project-Id, and X-Environment headers are required.",
            request_id=request_id,
            details={"required_headers": ["X-Tenant-Id", "X-Project-Id", "X-Environment"]},
        )
    actor = authenticate_api_key(
        authorization=authorization,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        required_scope="agent:read",
        request_id=request_id,
    )
    if isinstance(actor, JSONResponse):
        return actor
    return tenant_id, project_id, environment


def collect_runtime_metrics_snapshot(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    tenant_id: int,
    project_id: int,
    environment: str,
    now: datetime | None = None,
) -> RuntimeMetricsSnapshotRead:
    current = now or datetime.now(UTC)
    scoped_deployments = [
        deployment
        for deployment in deployments.deployments.list(tenant_id=tenant_id, project_id=project_id)
        if deployment.environment == environment
    ]
    deployment_ids = {deployment.id for deployment in scoped_deployments}
    runs = [
        run
        for run in runtime.list_runs(tenant_id=tenant_id, project_id=project_id)
        if run.deployment_id in deployment_ids
    ]
    tasks = [
        task
        for task in runtime.list_tasks(tenant_id=tenant_id, project_id=project_id)
        if task.run_id in {run.id for run in runs}
    ]
    worker_views = build_worker_health_views(
        runtime=runtime,
        deployments=deployments,
        workers=default_worker_registry(),
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
        now=current,
    )
    queue_groups: dict[str, list[Any]] = defaultdict(list)
    for task in tasks:
        queue_groups[task.queue].append(task)
    queues = [
        RuntimeQueueMetricsRead(
            queue=queue,
            queue_backlog=sum(
                1 for task in queue_tasks if task.status in {TaskStatus.queued, TaskStatus.retrying}
            ),
            running_tasks=sum(1 for task in queue_tasks if task.status == TaskStatus.running),
            leased_tasks=sum(1 for task in queue_tasks if task.status == TaskStatus.leased),
            retrying_tasks=sum(1 for task in queue_tasks if task.status == TaskStatus.retrying),
            dead_letters=sum(1 for task in queue_tasks if task.status == TaskStatus.dead_letter),
            oldest_task_age_seconds=_oldest_task_age_seconds(queue_tasks, current),
        )
        for queue, queue_tasks in sorted(queue_groups.items())
    ]
    latencies = sorted(
        int((run.finished_at - run.started_at).total_seconds() * 1000)
        for run in runs
        if run.started_at is not None and run.finished_at is not None
    )
    completed_runs = [
        run
        for run in runs
        if run.status in {RunStatus.succeeded, RunStatus.failed, RunStatus.timeout}
    ]
    succeeded_runs = [run for run in runs if run.status == RunStatus.succeeded]
    failed_runs = [run for run in runs if run.status == RunStatus.failed]
    summary = RuntimeMetricsSummaryRead(
        run_count_today=len(runs),
        success_rate=(len(succeeded_runs) / len(completed_runs)) if completed_runs else 0.0,
        p95_latency_ms=_percentile(latencies, 0.95),
        p99_latency_ms=_percentile(latencies, 0.99),
        queue_backlog=sum(queue.queue_backlog + queue.dead_letters for queue in queues),
        running_tasks=sum(queue.running_tasks for queue in queues),
        worker_ready=sum(1 for worker in worker_views if worker["readiness"] == "ready"),
        worker_total=len(worker_views),
        dead_letters=sum(queue.dead_letters for queue in queues),
        retries=sum(queue.retrying_tasks for queue in queues),
        active_incidents=_active_incident_count(
            runtime=runtime,
            tenant_id=tenant_id,
            project_id=project_id,
            failed_runs=failed_runs,
        ),
        active_workers=sum(1 for worker in worker_views if worker["liveness"] == "alive"),
        failed_runs=len(failed_runs),
        monthly_cost_usd=0.0,
        pending_approvals=0,
    )
    return RuntimeMetricsSnapshotRead(
        summary=summary,
        queues=queues,
        workers=[
            RuntimeWorkerMetricsRead(
                worker_id=str(worker["worker_id"]),
                heartbeat_age_seconds=(
                    float(worker["heartbeat_age_seconds"])
                    if worker["heartbeat_age_seconds"] is not None
                    else None
                ),
                readiness=str(worker["readiness"]),
                liveness=str(worker["liveness"]),
                active_attempts=int(worker["active_attempts"]),
                retrying_tasks=int(worker["retrying_tasks"]),
                dead_letter_tasks=int(worker["dead_letter_tasks"]),
            )
            for worker in worker_views
        ],
        active_incidents=[
            RuntimeIncidentRead(
                run_id=run.id,
                status=run.status.value,
                error_summary=_error_summary(run.error),
                created_at=run.created_at.isoformat(),
            )
            for run in sorted(failed_runs, key=lambda item: item.created_at, reverse=True)[:10]
        ],
        trend_points=_trend_points(runs),
    )


@router.get("/v1/runtime/metrics/summary", response_model=RuntimeMetricsSnapshotRead)
def get_runtime_metrics_summary(
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> RuntimeMetricsSnapshotRead | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id, environment = auth
    return collect_runtime_metrics_snapshot(
        runtime=runtime,
        deployments=default_deployment_control(),
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )


@router.get("/v1/runtime/events", response_model=list[RuntimeEventQueryRead])
def query_runtime_events(
    runtime: NativeRuntimeDep,
    event_type: Annotated[str | None, Query()] = None,
    visibility_level: Annotated[str | None, Query()] = None,
    trace_id: Annotated[str | None, Query()] = None,
    request_id: Annotated[str | None, Query()] = None,
    redact: Annotated[bool, Query()] = True,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[RuntimeEventQueryRead] | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id, environment = auth
    _ = environment
    result: list[RuntimeEventQueryRead] = []
    for event in runtime.list_events(tenant_id=tenant_id, project_id=project_id):
        payload = dict(event.payload or {})
        payload_trace_id = _optional_string(payload.get("trace_id"))
        payload_request_id = _optional_string(payload.get("request_id"))
        if event_type is not None and event.type != event_type:
            continue
        if visibility_level is not None and event.visibility_level != visibility_level:
            continue
        if trace_id is not None and payload_trace_id != trace_id:
            continue
        if request_id is not None and payload_request_id != request_id:
            continue
        result.append(
            RuntimeEventQueryRead(
                run_id=int(event.run_id or 0),
                event_id=str(event.event_id or ""),
                sequence=int(event.sequence or 0),
                type=event.type,
                visibility_level=event.visibility_level,
                trace_id=payload_trace_id,
                request_id=payload_request_id,
                payload=(
                    redact_event_payload(payload, visibility_level=event.visibility_level)
                    if redact
                    else payload
                ),
            )
        )
    return result


@router.get("/metrics", response_class=PlainTextResponse, response_model=None)
def prometheus_metrics(
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> PlainTextResponse | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        environment=x_environment,
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id, environment = auth
    snapshot = collect_runtime_metrics_snapshot(
        runtime=runtime,
        deployments=default_deployment_control(),
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    return PlainTextResponse(render_prometheus_metrics(snapshot.model_dump(mode="python")))


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    index = min(len(values) - 1, round((len(values) - 1) * percentile))
    return values[index]


def _oldest_task_age_seconds(tasks: list[Any], current: datetime) -> float | None:
    created_at = min((task.created_at for task in tasks), default=None)
    if created_at is None:
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return float((current - created_at).total_seconds())


def _trend_points(runs: list[Any]) -> list[RuntimeTrendPointRead]:
    buckets: dict[str, list[Any]] = defaultdict(list)
    for run in sorted(runs, key=lambda item: item.created_at)[-24:]:
        buckets[run.created_at.strftime("%m-%d %H:00")].append(run)
    points: list[RuntimeTrendPointRead] = []
    for label, bucket in list(buckets.items())[-12:]:
        completed = [
            run
            for run in bucket
            if run.status in {RunStatus.succeeded, RunStatus.failed, RunStatus.timeout}
        ]
        succeeded = [run for run in bucket if run.status == RunStatus.succeeded]
        points.append(
            RuntimeTrendPointRead(
                label=label,
                runs=len(bucket),
                success_rate=(len(succeeded) / len(completed)) if completed else 0.0,
            )
        )
    return points


def _active_incident_count(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    tenant_id: int,
    project_id: int,
    failed_runs: list[Any],
) -> int:
    if not isinstance(runtime, SQLAlchemyNativeRuntimeStore):
        return len(failed_runs)
    incidents = list(
        runtime.session.scalars(
            select(IncidentEvent).where(
                IncidentEvent.tenant_id == tenant_id,
                IncidentEvent.project_id == project_id,
                IncidentEvent.status != "resolved",
            )
        )
    )
    return max(len(incidents), len(failed_runs))


def _error_summary(error: dict[str, Any] | None) -> str:
    if not error:
        return "Run failed."
    message = error.get("message")
    return str(message) if isinstance(message, str) and message else "Run failed."


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
