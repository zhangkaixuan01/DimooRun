from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

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
from dimoo_run.core.events import AgentEvent
from dimoo_run.domain.models import ModelUsageSnapshot, RunAttempt
from dimoo_run.persistence.repositories import AuditLogRepository, EventRepository

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


class IntegrationTraceLink(BaseModel):
    provider: str
    url: str
    trace_id: str | None = None
    label: str | None = None
    status: str = "linked"


class IntegrationExporterEvidence(BaseModel):
    provider: str
    exporter_type: str | None = None
    target_ref: str | None = None
    status: str
    request_id: str | None = None
    delivered_at: datetime | None = None
    message: str | None = None


class IntegrationModelGatewayEvidence(BaseModel):
    provider: str
    gateway_id: int | None = None
    gateway_name: str | None = None
    gateway_request_id: str | None = None
    model: str | None = None
    route: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost: float | None = None
    currency: str = "USD"


class IntegrationFailureEvidence(BaseModel):
    provider: str
    status: str = "failed"
    error_code: str | None = None
    message: str
    retryable: bool | None = None
    occurred_at: datetime | None = None


class RunIntegrationEvidenceRecord(BaseModel):
    evidence_id: str
    source: str
    observed_at: datetime
    trace_links: list[IntegrationTraceLink] = []
    exporters: list[IntegrationExporterEvidence] = []
    model_gateway: IntegrationModelGatewayEvidence | None = None
    failures: list[IntegrationFailureEvidence] = []
    raw: dict[str, Any] = {}


class RunIntegrationEvidenceWrite(BaseModel):
    source: str = "api"
    observed_at: datetime | None = None
    trace_links: list[IntegrationTraceLink] = []
    exporters: list[IntegrationExporterEvidence] = []
    model_gateway: IntegrationModelGatewayEvidence | None = None
    failures: list[IntegrationFailureEvidence] = []
    raw: dict[str, Any] = {}


class RunIntegrationEvidenceRead(BaseModel):
    run_id: int
    trace_links: list[IntegrationTraceLink] = []
    exporters: list[IntegrationExporterEvidence] = []
    model_gateway: list[IntegrationModelGatewayEvidence] = []
    failures: list[IntegrationFailureEvidence] = []
    records: list[RunIntegrationEvidenceRecord] = []


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


def _event_record(event: AgentEvent) -> RunIntegrationEvidenceRecord | None:
    if event.type != "integration.evidence.recorded":
        return None
    payload = event.payload or {}
    if payload.get("schema") != "dimoorun.run.integration_evidence.v1":
        return None
    return RunIntegrationEvidenceRecord.model_validate(
        {
            "evidence_id": payload.get("evidence_id") or event.event_id or "",
            "source": payload.get("source") or "event",
            "observed_at": payload.get("observed_at") or event.created_at,
            "trace_links": payload.get("trace_links") or [],
            "exporters": payload.get("exporters") or [],
            "model_gateway": payload.get("model_gateway"),
            "failures": payload.get("failures") or [],
            "raw": payload.get("raw") or {},
        }
    )


def _aggregate_integration_evidence(
    run: NativeRun,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
) -> RunIntegrationEvidenceRead:
    records = [
        record
        for event in runtime.list_run_events(run.id)
        if (record := _event_record(event)) is not None
    ]
    model_gateway = [
        record.model_gateway for record in records if record.model_gateway is not None
    ]
    if isinstance(runtime, SQLAlchemyNativeRuntimeStore):
        snapshots = runtime.session.scalars(
            select(ModelUsageSnapshot)
            .where(ModelUsageSnapshot.run_id == run.id)
            .order_by(ModelUsageSnapshot.created_at, ModelUsageSnapshot.id)
        )
        model_gateway.extend(
            IntegrationModelGatewayEvidence(
                provider=snapshot.provider or "model_gateway",
                gateway_id=snapshot.gateway_id,
                gateway_request_id=snapshot.gateway_request_id,
                model=snapshot.model,
                prompt_tokens=snapshot.prompt_tokens,
                completion_tokens=snapshot.completion_tokens,
                total_tokens=snapshot.total_tokens,
                cost=snapshot.cost,
                currency=snapshot.currency,
            )
            for snapshot in snapshots
        )
    return RunIntegrationEvidenceRead(
        run_id=run.id,
        trace_links=[item for record in records for item in record.trace_links],
        exporters=[item for record in records for item in record.exporters],
        model_gateway=model_gateway,
        failures=[item for record in records for item in record.failures],
        records=records,
    )


def _integration_event_payload(
    payload: RunIntegrationEvidenceWrite,
) -> dict[str, Any]:
    record = RunIntegrationEvidenceRecord(
        evidence_id=f"intev_{uuid4().hex[:12]}",
        source=payload.source,
        observed_at=payload.observed_at or datetime.utcnow(),
        trace_links=payload.trace_links,
        exporters=payload.exporters,
        model_gateway=payload.model_gateway,
        failures=payload.failures,
        raw=payload.raw,
    )
    event_payload = record.model_dump(mode="json")
    event_payload["schema"] = "dimoorun.run.integration_evidence.v1"
    return event_payload


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


@router.get("/runs/{run_id}/integration-evidence", response_model=RunIntegrationEvidenceRead)
def get_run_integration_evidence(
    run_id: int,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> RunIntegrationEvidenceRead | JSONResponse:
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
    return _aggregate_integration_evidence(run, runtime)


@router.post("/runs/{run_id}/integration-evidence", response_model=RunIntegrationEvidenceRead)
def record_run_integration_evidence(
    run_id: int,
    runtime: NativeRuntimeDep,
    payload: RunIntegrationEvidenceWrite,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> RunIntegrationEvidenceRead | JSONResponse:
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
    event_payload = _integration_event_payload(payload)
    if isinstance(runtime, SQLAlchemyNativeRuntimeStore):
        EventRepository(runtime.session).append(
            event_id=event_payload["evidence_id"],
            run_id=run.id,
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            type="integration.evidence.recorded",
            payload=event_payload,
            visibility_level="public",
        )
        AuditLogRepository(runtime.session).append(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            action="run.integration_evidence.record",
            resource_type="run",
            resource_id=run.id,
            result="allow",
            request_id=x_request_id,
            metadata=event_payload,
        )
        if payload.model_gateway and payload.model_gateway.gateway_id is not None:
            runtime.session.add(
                ModelUsageSnapshot(
                    tenant_id=run.tenant_id,
                    project_id=run.project_id,
                    run_id=run.id,
                    gateway_id=payload.model_gateway.gateway_id,
                    gateway_request_id=payload.model_gateway.gateway_request_id,
                    model=payload.model_gateway.model or "unknown",
                    provider=payload.model_gateway.provider,
                    prompt_tokens=payload.model_gateway.prompt_tokens or 0,
                    completion_tokens=payload.model_gateway.completion_tokens or 0,
                    total_tokens=payload.model_gateway.total_tokens or 0,
                    cost=payload.model_gateway.cost or 0,
                    currency=payload.model_gateway.currency,
                    raw_usage_json=payload.model_gateway.model_dump(mode="json"),
                )
            )
        runtime.session.flush()
    else:
        runtime.replay_buffer.append(
            run.id,
            None,
            AgentEvent(
                type="integration.evidence.recorded",
                payload=event_payload,
                visibility_level="public",
            ),
        )
    return _aggregate_integration_evidence(run, runtime)


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
