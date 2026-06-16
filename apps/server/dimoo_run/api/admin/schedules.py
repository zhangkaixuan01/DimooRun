from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    enforce_console_actor,
)
from dimoo_run.api.native.dependencies import get_native_runtime
from dimoo_run.api.native.deployments import DeploymentControlDep
from dimoo_run.api.native.runtime import NativeRuntimeStore, SQLAlchemyNativeRuntimeStore
from dimoo_run.core.config import Settings
from dimoo_run.domain.models import ScheduledRuns
from dimoo_run.persistence.database import Base, create_session_factory
from dimoo_run.runtime.scheduled_runs import (
    compute_next_fire_time,
    resolve_due_fire_times,
    validate_schedule_payload,
)

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]
NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]


def _parse_datetime(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _apply_schedule_metadata(record: ScheduledRuns) -> dict[str, Any]:
    metadata = dict(record.metadata_json or {})
    record.schedule_type = str(metadata.get("schedule_type") or "").strip() or None
    record.timezone = str(metadata.get("timezone") or "UTC").strip() or "UTC"
    record.next_fire_at = _parse_datetime(metadata.get("next_fire_time"))
    record.last_triggered_at = _parse_datetime(metadata.get("last_triggered_at"))
    record.last_run_id = int(metadata["last_run_id"]) if metadata.get("last_run_id") else None
    record.last_task_id = int(metadata["last_task_id"]) if metadata.get("last_task_id") else None
    record.last_run_status = str(metadata.get("last_run_status") or "").strip() or None
    record.missed_run_policy = str(metadata.get("missed_run_policy") or "skip")
    record.backfill_policy = str(metadata.get("backfill_policy") or "none")
    record.pause_reason = str(metadata.get("pause_reason") or "").strip() or None
    record.trigger_count = int(metadata.get("trigger_count") or 0)
    return metadata


def _persist_schedule_metadata(record: ScheduledRuns, metadata: dict[str, Any]) -> None:
    if record.schedule_type:
        metadata["schedule_type"] = record.schedule_type
    metadata["timezone"] = record.timezone
    metadata["next_fire_time"] = (
        record.next_fire_at.astimezone(UTC).isoformat() if record.next_fire_at else None
    )
    metadata["last_triggered_at"] = (
        record.last_triggered_at.astimezone(UTC).isoformat()
        if record.last_triggered_at
        else None
    )
    metadata["last_run_id"] = record.last_run_id
    metadata["last_task_id"] = record.last_task_id
    metadata["last_run_status"] = record.last_run_status
    metadata["missed_run_policy"] = record.missed_run_policy
    metadata["backfill_policy"] = record.backfill_policy
    metadata["pause_reason"] = record.pause_reason
    metadata["trigger_count"] = record.trigger_count
    record.metadata_json = metadata

def _session() -> Session:
    session_factory = create_session_factory(Settings.from_env().database.url)
    session = session_factory()
    if Settings.from_env().runtime.mode == "dev":
        Base.metadata.create_all(session.get_bind())
    return session


def _require_scope(
    tenant_id: int | None,
    project_id: int | None,
) -> tuple[int, int] | JSONResponse:
    if tenant_id is not None and project_id is not None:
        return tenant_id, project_id
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "scope_headers_required",
            "message": "X-Tenant-Id and X-Project-Id are required.",
        },
    )


def _session_for_runtime(
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
) -> Session:
    if isinstance(runtime, SQLAlchemyNativeRuntimeStore):
        return runtime.session
    return _session()


def _require_audit_reason(payload: dict[str, Any], request_id: str | None) -> JSONResponse | None:
    reason = str(payload.get("audit_reason") or "").strip()
    if reason:
        return None
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "audit_reason_required",
            "message": "Schedule workflow writes require an audit_reason.",
            "request_id": request_id,
        },
    )


def _schedule_item(record: ScheduledRuns) -> dict[str, Any]:
    metadata = _apply_schedule_metadata(record)
    return {
        "id": record.id,
        "name": metadata.get("name"),
        "status": record.status,
        "schedule_type": record.schedule_type,
        "cron_expression": metadata.get("cron_expression"),
        "interval_minutes": metadata.get("interval_minutes"),
        "timezone": record.timezone,
        "next_fire_time": metadata.get("next_fire_time"),
        "next_fire_at": record.next_fire_at.isoformat() if record.next_fire_at else None,
        "deployment_id": metadata.get("deployment_id"),
        "input_template": metadata.get("input_template") or {},
        "backfill_policy": record.backfill_policy,
        "missed_run_policy": record.missed_run_policy,
        "last_triggered_at": (
            record.last_triggered_at.isoformat() if record.last_triggered_at else None
        ),
        "last_run_id": record.last_run_id,
        "last_task_id": record.last_task_id,
        "last_run_status": record.last_run_status,
        "last_task_status": metadata.get("last_task_status"),
        "last_trigger_source": metadata.get("last_trigger_source"),
        "trigger_count": record.trigger_count,
        "pause_reason": record.pause_reason,
        "tenant_id": record.tenant_id,
        "project_id": record.project_id,
        "environment": metadata.get("environment"),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "metadata": {key: value for key, value in metadata.items() if key not in {
            "name",
            "schedule_type",
            "cron_expression",
            "interval_minutes",
            "timezone",
            "next_fire_time",
            "deployment_id",
            "input_template",
            "backfill_policy",
            "missed_run_policy",
            "last_triggered_at",
            "last_run_id",
            "last_task_id",
            "pause_reason",
            "environment",
            "agent_id",
            "agent_version_id",
        }},
    }


def _refresh_schedule_record(
    record: ScheduledRuns,
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    tenant_id: int,
    project_id: int,
) -> None:
    metadata = _apply_schedule_metadata(record)
    changed = False
    if isinstance(record.last_run_id, int):
        run = runtime.get_run(record.last_run_id, tenant_id=tenant_id, project_id=project_id)
        next_status = run.status.value if run is not None else None
        if record.last_run_status != next_status:
            record.last_run_status = next_status
            changed = True
    if isinstance(record.last_task_id, int):
        task = runtime.get_task(record.last_task_id, tenant_id=tenant_id, project_id=project_id)
        next_status = task.status.value if task is not None else None
        if metadata.get("last_task_status") != next_status:
            metadata["last_task_status"] = next_status
            changed = True
    if changed:
        _persist_schedule_metadata(record, metadata)


def _create_scheduled_runtime_run(
    record: ScheduledRuns,
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    service: DeploymentControlDep,
    tenant_id: int,
    project_id: int,
    input_payload: dict[str, Any],
    audit_reason: str | None,
    trigger_source: str,
    endpoint: str,
    fire_time: str | None = None,
) -> tuple[Any, Any]:
    metadata = dict(record.metadata_json or {})
    try:
        deployment = service.deployments.get(int(metadata.get("deployment_id") or 0))
    except Exception:
        deployment = None
    if deployment is None:
        raise LookupError("deployment_not_found")
    agent = runtime.get_agent(
        deployment.agent_id,
        tenant_id=tenant_id,
        project_id=project_id,
    )
    agent_version = runtime.get_version_by_id(
        deployment.agent_id,
        deployment.agent_version_id,
    )
    if agent is None or agent_version is None:
        raise ValueError("schedule_binding_invalid")
    run, task, _ = runtime.create_task_run(
        tenant_id=tenant_id,
        project_id=project_id,
        agent=agent,
        agent_version=agent_version,
        input_data=input_payload,
        thread_id=None,
        idempotency_key=None,
        endpoint=endpoint,
        request_body={
            "schedule_id": record.id,
            "input": input_payload,
            "audit_reason": audit_reason,
            "fire_time": fire_time,
            "trigger_source": trigger_source,
        },
        deployment_id=deployment.id,
    )
    return run, task


@router.post("/v1/schedules/preview")
def preview_schedule(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
) -> Any:
    try:
        normalized, preview = validate_schedule_payload(payload or {})
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": str(exc),
                "message": "Schedule preview payload is invalid.",
                "request_id": x_request_id,
            },
        )
    return {
        "preview": {
            "schedule_type": preview.schedule_type,
            "timezone": preview.timezone,
            "cron_expression": preview.cron_expression,
            "interval_minutes": preview.interval_minutes,
            "next_fire_time": preview.next_fire_time,
        },
        "normalized": normalized,
        "request_id": x_request_id,
    }


@router.post("/v1/schedules", status_code=status.HTTP_201_CREATED)
def create_schedule(
    service: DeploymentControlDep,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    data = payload or {}
    audit_error = _require_audit_reason(data, x_request_id)
    if audit_error is not None:
        return audit_error
    try:
        normalized, preview = validate_schedule_payload(data)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": str(exc),
                "message": "Schedule payload is invalid.",
                "request_id": x_request_id,
            },
        )
    scope = _require_scope(x_tenant_id, x_project_id)
    if isinstance(scope, JSONResponse):
        return scope
    tenant_id, project_id = scope
    try:
        deployment = service.deployments.get(int(normalized["deployment_id"]))
    except Exception:
        deployment = None
    if (
        deployment is None
        or deployment.tenant_id != tenant_id
        or deployment.project_id != project_id
        or deployment.environment != x_environment
    ):
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "deployment_not_found",
                "message": "Schedule deployment binding was not found in scope.",
                "request_id": x_request_id,
            },
        )
    session = _session()
    try:
        metadata = {
            **normalized,
            "next_fire_time": preview.next_fire_time,
            "environment": x_environment,
            "agent_id": deployment.agent_id,
            "agent_version_id": deployment.agent_version_id,
        }
        record = ScheduledRuns(
            tenant_id=tenant_id,
            project_id=project_id,
            status="active",
            metadata_json=metadata,
        )
        _apply_schedule_metadata(record)
        session.add(record)
        session.commit()
        session.refresh(record)
        return {"item": _schedule_item(record), "request_id": x_request_id}
    finally:
        session.close()


@router.get("/v1/schedules")
def list_schedules(
    runtime: NativeRuntimeDep,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    scope = _require_scope(x_tenant_id, x_project_id)
    if isinstance(scope, JSONResponse):
        return scope
    tenant_id, project_id = scope
    session = _session()
    try:
        records = (
            session.query(ScheduledRuns)
            .filter(
                ScheduledRuns.is_deleted.is_(False),
                ScheduledRuns.tenant_id == tenant_id,
                ScheduledRuns.project_id == project_id,
            )
            .order_by(ScheduledRuns.id.asc())
            .all()
        )
        for record in records:
            _refresh_schedule_record(
                record,
                runtime=runtime,
                tenant_id=tenant_id,
                project_id=project_id,
            )
        session.commit()
        items = [_schedule_item(record) for record in records]
        return {"items": items, "count": len(items), "request_id": x_request_id}
    finally:
        session.close()


@router.get("/v1/schedules/{schedule_id}")
def get_schedule(
    schedule_id: int,
    runtime: NativeRuntimeDep,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    scope = _require_scope(x_tenant_id, x_project_id)
    if isinstance(scope, JSONResponse):
        return scope
    tenant_id, project_id = scope
    session = _session()
    try:
        record = session.get(ScheduledRuns, schedule_id)
        if (
            record is None
            or record.is_deleted
            or record.tenant_id != tenant_id
            or record.project_id != project_id
        ):
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "schedule_not_found",
                    "message": "Schedule was not found.",
                    "request_id": x_request_id,
                },
            )
        _refresh_schedule_record(
            record,
            runtime=runtime,
            tenant_id=tenant_id,
            project_id=project_id,
        )
        session.commit()
        return {"item": _schedule_item(record), "request_id": x_request_id}
    finally:
        session.close()


def _update_schedule_status(
    schedule_id: int,
    *,
    status_value: str,
    payload: dict[str, Any],
    request_id: str | None,
    tenant_id: int | None,
    project_id: int | None,
) -> Any:
    audit_error = _require_audit_reason(payload, request_id)
    if audit_error is not None:
        return audit_error
    session = _session()
    try:
        record = session.get(ScheduledRuns, schedule_id)
        if (
            record is None
            or record.is_deleted
            or record.tenant_id != tenant_id
            or record.project_id != project_id
        ):
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "schedule_not_found",
                    "message": "Schedule was not found.",
                    "request_id": request_id,
                },
            )
        metadata = _apply_schedule_metadata(record)
        record.pause_reason = (
            str(payload.get("pause_reason") or "").strip() or None
            if status_value == "paused"
            else None
        )
        metadata["next_fire_time"] = compute_next_fire_time(metadata)
        record.next_fire_at = _parse_datetime(metadata["next_fire_time"])
        record.status = status_value
        _persist_schedule_metadata(record, metadata)
        session.commit()
        session.refresh(record)
        return {"item": _schedule_item(record), "request_id": request_id}
    finally:
        session.close()


@router.post("/v1/schedules/{schedule_id}/pause")
def pause_schedule(
    schedule_id: int,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    scope = _require_scope(x_tenant_id, x_project_id)
    if isinstance(scope, JSONResponse):
        return scope
    tenant_id, project_id = scope
    return _update_schedule_status(
        schedule_id,
        status_value="paused",
        payload=payload or {},
        request_id=x_request_id,
        tenant_id=tenant_id,
        project_id=project_id,
    )


@router.post("/v1/schedules/{schedule_id}/resume")
def resume_schedule(
    schedule_id: int,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    scope = _require_scope(x_tenant_id, x_project_id)
    if isinstance(scope, JSONResponse):
        return scope
    tenant_id, project_id = scope
    return _update_schedule_status(
        schedule_id,
        status_value="active",
        payload=payload or {},
        request_id=x_request_id,
        tenant_id=tenant_id,
        project_id=project_id,
    )


@router.post("/v1/schedules/{schedule_id}/trigger")
def trigger_schedule(
    schedule_id: int,
    runtime: NativeRuntimeDep,
    service: DeploymentControlDep,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    data = payload or {}
    audit_error = _require_audit_reason(data, x_request_id)
    if audit_error is not None:
        return audit_error
    scope = _require_scope(x_tenant_id, x_project_id)
    if isinstance(scope, JSONResponse):
        return scope
    tenant_id, project_id = scope
    session = _session_for_runtime(runtime)
    should_close_session = not isinstance(runtime, SQLAlchemyNativeRuntimeStore)
    try:
        record = session.get(ScheduledRuns, schedule_id)
        if (
            record is None
            or record.is_deleted
            or record.tenant_id != tenant_id
            or record.project_id != project_id
        ):
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "schedule_not_found",
                    "message": "Schedule was not found.",
                    "request_id": x_request_id,
                },
            )
        metadata = _apply_schedule_metadata(record)
        input_payload = data.get("input")
        if not isinstance(input_payload, dict):
            input_payload = dict(metadata.get("input_template") or {})
        try:
            run, task = _create_scheduled_runtime_run(
                record,
                runtime=runtime,
                service=service,
                tenant_id=tenant_id,
                project_id=project_id,
                input_payload=input_payload,
                audit_reason=str(data.get("audit_reason") or ""),
                trigger_source="manual",
                endpoint=f"/v1/schedules/{schedule_id}/trigger",
            )
        except LookupError:
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "deployment_not_found",
                    "message": "Schedule deployment binding was not found.",
                    "request_id": x_request_id,
                },
            )
        except ValueError:
            return JSONResponse(
                status_code=409,
                content={
                    "error_code": "schedule_binding_invalid",
                    "message": "Schedule binding no longer resolves to an active agent version.",
                    "request_id": x_request_id,
                },
            )
        record.last_triggered_at = datetime.now(UTC)
        record.last_run_id = run.id
        record.last_task_id = task.id
        record.last_run_status = run.status.value
        metadata["last_task_status"] = task.status.value
        metadata["last_trigger_source"] = "manual"
        record.trigger_count += 1
        metadata["next_fire_time"] = compute_next_fire_time(metadata)
        record.next_fire_at = _parse_datetime(metadata["next_fire_time"])
        _persist_schedule_metadata(record, metadata)
        session.commit()
        session.refresh(record)
        return {
            "item": _schedule_item(record),
            "triggered_run": {"run_id": run.id, "task_id": task.id, "status": task.status.value},
            "request_id": x_request_id,
        }
    finally:
        if should_close_session:
            session.close()


@router.post("/v1/schedules/run-due")
def run_due_schedules(
    runtime: NativeRuntimeDep,
    service: DeploymentControlDep,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    data = payload or {}
    audit_error = _require_audit_reason(data, x_request_id)
    if audit_error is not None:
        return audit_error
    scope = _require_scope(x_tenant_id, x_project_id)
    if isinstance(scope, JSONResponse):
        return scope
    tenant_id, project_id = scope
    session = _session_for_runtime(runtime)
    should_close_session = not isinstance(runtime, SQLAlchemyNativeRuntimeStore)
    try:
        records = (
            session.query(ScheduledRuns)
            .filter(
                ScheduledRuns.is_deleted.is_(False),
                ScheduledRuns.tenant_id == tenant_id,
                ScheduledRuns.project_id == project_id,
                ScheduledRuns.status == "active",
            )
            .order_by(ScheduledRuns.id.asc())
            .all()
        )
        triggered: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        for record in records:
            metadata = _apply_schedule_metadata(record)
            if metadata.get("environment") != x_environment:
                continue
            due_fire_times, next_fire_time = resolve_due_fire_times(
                metadata,
                status=record.status,
                now=now,
            )
            if not due_fire_times:
                metadata["next_fire_time"] = next_fire_time
                record.next_fire_at = _parse_datetime(next_fire_time)
                _persist_schedule_metadata(record, metadata)
                skipped.append({"schedule_id": record.id, "next_fire_time": next_fire_time})
                continue
            input_payload = dict(metadata.get("input_template") or {})
            run_ids: list[int] = []
            task_ids: list[int] = []
            last_run = None
            last_task = None
            for fire_time in due_fire_times:
                try:
                    last_run, last_task = _create_scheduled_runtime_run(
                        record,
                        runtime=runtime,
                        service=service,
                        tenant_id=tenant_id,
                        project_id=project_id,
                        input_payload=input_payload,
                        audit_reason=str(data.get("audit_reason") or ""),
                        trigger_source="automatic",
                        endpoint="/v1/schedules/run-due",
                        fire_time=fire_time,
                    )
                except (LookupError, ValueError):
                    return JSONResponse(
                        status_code=409,
                        content={
                            "error_code": "schedule_due_trigger_failed",
                            "message": f"Failed to trigger due schedule {record.id}.",
                            "schedule_id": record.id,
                            "request_id": x_request_id,
                        },
                    )
                run_ids.append(last_run.id)
                task_ids.append(last_task.id)
            record.last_triggered_at = now
            record.last_run_id = last_run.id if last_run is not None else record.last_run_id
            record.last_task_id = last_task.id if last_task is not None else record.last_task_id
            record.last_run_status = (
                last_run.status.value if last_run is not None else record.last_run_status
            )
            metadata["last_task_status"] = (
                last_task.status.value
                if last_task is not None
                else metadata.get("last_task_status")
            )
            metadata["last_trigger_source"] = "automatic"
            record.trigger_count += len(due_fire_times)
            metadata["next_fire_time"] = next_fire_time
            record.next_fire_at = _parse_datetime(next_fire_time)
            _persist_schedule_metadata(record, metadata)
            triggered.append(
                {
                    "schedule_id": record.id,
                    "triggered_count": len(due_fire_times),
                    "run_ids": run_ids,
                    "task_ids": task_ids,
                    "next_fire_time": next_fire_time,
                }
            )
        session.commit()
        return {
            "triggered": triggered,
            "skipped": skipped,
            "count": len(triggered),
            "request_id": x_request_id,
        }
    finally:
        if should_close_session:
            session.close()
