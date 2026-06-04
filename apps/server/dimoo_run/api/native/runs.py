from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from dimoo_run.api.compat.auth import ProjectIdHeader, TenantIdHeader
from dimoo_run.api.dependencies import (
    AuthorizationHeader,
    RequestIdHeader,
    authenticate_api_key,
    error_response,
)
from dimoo_run.api.native.dependencies import get_native_runtime
from dimoo_run.api.native.runtime import (
    NativeRun,
    NativeRuntimeStore,
    SQLAlchemyNativeRuntimeStore,
)
from dimoo_run.domain.models import RunAttempt

router = APIRouter(tags=["native-runs"])
NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]


class RunRead(BaseModel):
    id: int
    tenant_id: int
    project_id: int
    agent_id: int
    agent_version_id: int
    deployment_id: int | None
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    thread_id: str | None = None
    idempotency_key: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latency_ms: int | None = None


class EventRead(BaseModel):
    run_id: int
    event_id: str
    sequence: int
    type: str
    payload: dict[str, Any]
    visibility_level: str


class RunAttemptRead(BaseModel):
    id: int
    run_id: int
    task_id: int | None
    attempt_no: int
    worker_id: str | None
    status: str
    error: str | None = None


class ReplayRunRequest(BaseModel):
    agent_version_id: int | None = None


def _auth(
    *,
    authorization: str | None,
    tenant_id: int | None,
    project_id: int | None,
    required_scope: str,
    request_id: str | None,
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


def _run_to_read(run: NativeRun) -> RunRead:
    payload = run.__dict__.copy()
    payload["status"] = run.status.value
    started_at = payload.get("started_at")
    finished_at = payload.get("finished_at")
    payload["latency_ms"] = (
        int((finished_at - started_at).total_seconds() * 1000)
        if started_at is not None and finished_at is not None
        else None
    )
    return RunRead.model_validate(payload)


def _find_run(
    run_id: int,
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    authorization: str | None,
    tenant_id: int | None,
    project_id: int | None,
    request_id: str | None,
    required_scope: str = "agent:read",
) -> NativeRun | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=tenant_id,
        project_id=project_id,
        required_scope=required_scope,
        request_id=request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    scoped_tenant_id, scoped_project_id = auth
    run = runtime.get_run(
        run_id,
        tenant_id=scoped_tenant_id,
        project_id=scoped_project_id,
    )
    if run is None:
        return error_response(
            status_code=404,
            error_code="run_not_found",
            message="Run was not found.",
            request_id=request_id,
            details={"run_id": run_id},
        )
    return run


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(
    run_id: int,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> RunRead | JSONResponse:
    run = _find_run(
        run_id,
        runtime=runtime,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if isinstance(run, JSONResponse):
        return run
    return _run_to_read(run)


@router.get("/runs", response_model=list[RunRead])
def list_runs(
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[RunRead] | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:read",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id = auth
    return [
        _run_to_read(run)
        for run in runtime.list_runs(tenant_id=tenant_id, project_id=project_id)
    ]


@router.get("/runs/{run_id}/events", response_model=list[EventRead])
def list_run_events(
    run_id: int,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[EventRead] | JSONResponse:
    run = _find_run(
        run_id,
        runtime=runtime,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if isinstance(run, JSONResponse):
        return run
    return [
            EventRead(
                run_id=event.run_id or run.id,
                event_id=event.event_id or "",
                sequence=event.sequence or 0,
                type=event.type,
            payload=event.payload,
            visibility_level=event.visibility_level,
        )
        for event in runtime.list_run_events(run.id)
    ]


@router.get("/events", response_model=list[EventRead])
def list_events(
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[EventRead] | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:read",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id = auth
    return [
        EventRead(
            run_id=event.run_id or 0,
            event_id=event.event_id or "",
            sequence=event.sequence or 0,
            type=event.type,
            payload=event.payload,
            visibility_level=event.visibility_level,
        )
        for event in runtime.list_events(tenant_id=tenant_id, project_id=project_id)
    ]


@router.get("/runs/{run_id}/attempts", response_model=list[RunAttemptRead])
def list_run_attempts(
    run_id: int,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[RunAttemptRead] | JSONResponse:
    run = _find_run(
        run_id,
        runtime=runtime,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if isinstance(run, JSONResponse):
        return run
    if isinstance(runtime, SQLAlchemyNativeRuntimeStore):
        attempts = runtime.session.scalars(
            select(RunAttempt)
            .where(RunAttempt.run_id == run.id, RunAttempt.is_deleted.is_(False))
            .order_by(RunAttempt.attempt_no)
        )
        return [RunAttemptRead.model_validate(attempt.__dict__) for attempt in attempts]
    return []


@router.post("/runs/{run_id}/cancel", response_model=RunRead)
def cancel_run(
    run_id: int,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> RunRead | JSONResponse:
    run = _find_run(
        run_id,
        runtime=runtime,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:invoke",
    )
    if isinstance(run, JSONResponse):
        return run
    cancelled = runtime.cancel_run(run)
    return _run_to_read(cancelled)


@router.post("/runs/{run_id}/resume", response_model=RunRead)
def resume_run(
    run_id: int,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> RunRead | JSONResponse:
    return get_run(run_id, runtime, authorization, x_tenant_id, x_project_id, x_request_id)


@router.post("/runs/{run_id}/retry", response_model=RunRead)
def retry_run(
    run_id: int,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> RunRead | JSONResponse:
    return get_run(run_id, runtime, authorization, x_tenant_id, x_project_id, x_request_id)


@router.post("/runs/{run_id}/replay", response_model=RunRead)
def replay_run(
    run_id: int,
    runtime: NativeRuntimeDep,
    payload: ReplayRunRequest | None = None,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> RunRead | JSONResponse:
    run = _find_run(
        run_id,
        runtime=runtime,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:invoke",
    )
    if isinstance(run, JSONResponse):
        return run
    try:
        replay = runtime.replay_run(
            run,
            agent_version_id=payload.agent_version_id if payload else None,
        )
    except KeyError:
        return error_response(
            status_code=404,
            error_code="agent_version_not_found",
            message="Agent version was not found.",
            request_id=x_request_id,
            details={
                "agent_id": run.agent_id,
                "agent_version_id": payload.agent_version_id if payload else None,
            },
        )
    return _run_to_read(replay)
