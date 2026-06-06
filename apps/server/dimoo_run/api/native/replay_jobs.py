from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dimoo_run.api.compat.auth import ProjectIdHeader, TenantIdHeader
from dimoo_run.api.dependencies import (
    AuthorizationHeader,
    RequestIdHeader,
    authenticate_api_key,
    error_response,
)
from dimoo_run.api.native.dependencies import get_native_runtime
from dimoo_run.api.native.runs import EventRead, RunRead, _run_to_read
from dimoo_run.api.native.runtime import NativeRuntimeStore, SQLAlchemyNativeRuntimeStore

router = APIRouter(tags=["native-replay-jobs"])
NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]


class ReplayComparisonRequest(BaseModel):
    source_run_id: int
    candidate_agent_version_id: int | None = None
    replay_config: dict[str, Any] = Field(default_factory=dict)


class DatasetCaptureRequest(BaseModel):
    dataset_name: str
    label: str | None = None


class ValueDiff(BaseModel):
    changed: bool
    source: Any = None
    replay: Any = None


class EventDiff(BaseModel):
    changed: bool
    source_count: int
    replay_count: int
    added_types: list[str]
    removed_types: list[str]


class ReplayComparisonRead(BaseModel):
    comparison_id: str
    source_run: RunRead
    replay_run: RunRead
    source_events: list[EventRead]
    replay_events: list[EventRead]
    input_diff: ValueDiff
    output_diff: ValueDiff
    error_diff: ValueDiff
    event_diff: EventDiff
    latency_delta_ms: int | None = None
    cost_delta_usd: float | None = None
    regression_signal: str
    provenance: dict[str, Any]


class DatasetCaptureRead(BaseModel):
    capture_id: str
    comparison_id: str
    dataset_name: str
    label: str | None
    source_run_id: int
    replay_run_id: int
    provenance: dict[str, Any]


_comparisons: dict[str, ReplayComparisonRead] = {}


def reset_replay_comparisons() -> None:
    _comparisons.clear()


def _auth(
    *,
    authorization: str | None,
    tenant_id: int | None,
    project_id: int | None,
    request_id: str | None,
    required_scope: str,
) -> tuple[int, int] | JSONResponse:
    if tenant_id is None or project_id is None:
        return error_response(
            status_code=400,
            error_code="request_scope_required",
            message="X-Tenant-Id and X-Project-Id headers are required.",
            request_id=request_id,
            details={"required_headers": ["X-Tenant-Id", "X-Project-Id"]},
        )
    actor = authenticate_api_key(
        authorization=authorization,
        tenant_id=tenant_id,
        project_id=project_id,
        required_scope=required_scope,
        request_id=request_id,
    )
    if isinstance(actor, JSONResponse):
        return actor
    return tenant_id, project_id


def _event_reads(
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    run_id: int,
) -> list[EventRead]:
    return [
        EventRead(
            run_id=event.run_id or run_id,
            event_id=event.event_id or "",
            sequence=event.sequence or 0,
            type=event.type,
            payload=event.payload,
            visibility_level=event.visibility_level,
        )
        for event in runtime.list_run_events(run_id)
    ]


def _value_diff(source: Any, replay: Any) -> ValueDiff:
    return ValueDiff(changed=source != replay, source=source, replay=replay)


def _event_diff(source_events: list[EventRead], replay_events: list[EventRead]) -> EventDiff:
    source_types = [event.type for event in source_events]
    replay_types = [event.type for event in replay_events]
    return EventDiff(
        changed=source_types != replay_types,
        source_count=len(source_events),
        replay_count=len(replay_events),
        added_types=[event_type for event_type in replay_types if event_type not in source_types],
        removed_types=[event_type for event_type in source_types if event_type not in replay_types],
    )


def _latency_delta(source: RunRead, replay: RunRead) -> int | None:
    if source.latency_ms is None or replay.latency_ms is None:
        return None
    return replay.latency_ms - source.latency_ms


@router.post(
    "/replay-jobs/compare",
    response_model=ReplayComparisonRead,
    status_code=status.HTTP_201_CREATED,
)
def create_replay_comparison(
    payload: ReplayComparisonRequest,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> ReplayComparisonRead | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:invoke",
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id = auth
    source = runtime.get_run(payload.source_run_id, tenant_id=tenant_id, project_id=project_id)
    if source is None:
        return error_response(
            status_code=404,
            error_code="run_not_found",
            message="Source run was not found.",
            request_id=x_request_id,
            details={"run_id": payload.source_run_id},
        )
    if payload.candidate_agent_version_id is not None:
        candidate = runtime.get_version_by_id(source.agent_id, payload.candidate_agent_version_id)
        if candidate is None:
            return error_response(
                status_code=404,
                error_code="agent_version_not_found",
                message="Candidate version was not found.",
                request_id=x_request_id,
                details={
                    "agent_id": source.agent_id,
                    "agent_version_id": payload.candidate_agent_version_id,
                },
            )
        if candidate.status != "ready":
            return error_response(
                status_code=409,
                error_code="agent_version_not_ready",
                message="Candidate version must be ready before replay comparison.",
                request_id=x_request_id,
                details={
                    "agent_id": source.agent_id,
                    "agent_version_id": payload.candidate_agent_version_id,
                    "status": candidate.status,
                },
            )
    try:
        replay = runtime.replay_run(
            source,
            agent_version_id=payload.candidate_agent_version_id,
        )
    except KeyError:
        return error_response(
            status_code=404,
            error_code="agent_version_not_found",
            message="Candidate version was not found.",
            request_id=x_request_id,
            details={
                "agent_id": source.agent_id,
                "agent_version_id": payload.candidate_agent_version_id,
            },
        )

    source_read = _run_to_read(source)
    replay_read = _run_to_read(replay)
    source_events = _event_reads(runtime, source.id)
    replay_events = _event_reads(runtime, replay.id)
    comparison_id = f"cmp_{uuid4().hex[:12]}"
    output_diff = _value_diff(source_read.output, replay_read.output)
    error_diff = _value_diff(source_read.error, replay_read.error)
    comparison = ReplayComparisonRead(
        comparison_id=comparison_id,
        source_run=source_read,
        replay_run=replay_read,
        source_events=source_events,
        replay_events=replay_events,
        input_diff=_value_diff(source_read.input, replay_read.input),
        output_diff=output_diff,
        error_diff=error_diff,
        event_diff=_event_diff(source_events, replay_events),
        latency_delta_ms=_latency_delta(source_read, replay_read),
        cost_delta_usd=None,
        regression_signal="changed" if output_diff.changed or error_diff.changed else "unchanged",
        provenance={
            "source_run_id": source.id,
            "replay_run_id": replay.id,
            "candidate_agent_version_id": replay.agent_version_id,
            "replay_config": payload.replay_config,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    _comparisons[comparison_id] = comparison
    return comparison


@router.post(
    "/replay-jobs/{comparison_id}/dataset-captures",
    response_model=DatasetCaptureRead,
    status_code=status.HTTP_201_CREATED,
)
def capture_replay_comparison_dataset(
    comparison_id: str,
    payload: DatasetCaptureRequest,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> DatasetCaptureRead | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:write",
    )
    if isinstance(auth, JSONResponse):
        return auth
    comparison = _comparisons.get(comparison_id)
    if comparison is None:
        return error_response(
            status_code=404,
            error_code="replay_comparison_not_found",
            message="Replay comparison was not found.",
            request_id=x_request_id,
            details={"comparison_id": comparison_id},
        )
    return DatasetCaptureRead(
        capture_id=f"dataset_capture_{uuid4().hex[:12]}",
        comparison_id=comparison_id,
        dataset_name=payload.dataset_name,
        label=payload.label,
        source_run_id=comparison.source_run.id,
        replay_run_id=comparison.replay_run.id,
        provenance={
            "comparison_id": comparison_id,
            "source_run_id": comparison.source_run.id,
            "replay_run_id": comparison.replay_run.id,
            "captured_at": datetime.now(UTC).isoformat(),
        },
    )
