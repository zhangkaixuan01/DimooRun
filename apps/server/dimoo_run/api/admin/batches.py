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
from dimoo_run.domain.enums import TaskStatus
from dimoo_run.domain.models import BatchRuns
from dimoo_run.persistence.database import Base, create_session_factory
from dimoo_run.runtime.batch_runs import (
    normalize_batch_items,
    normalize_batch_payload,
    overall_batch_status,
    summarize_batch_items,
)

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]
NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]

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


def _batch_item(record: BatchRuns) -> dict[str, Any]:
    metadata = dict(record.metadata_json or {})
    return {
        "id": record.id,
        "name": metadata.get("name"),
        "status": record.status,
        "deployment_id": metadata.get("deployment_id"),
        "dataset_id": metadata.get("dataset_id"),
        "concurrency": metadata.get("concurrency"),
        "retry_policy": metadata.get("retry_policy") or {},
        "cancel_policy": metadata.get("cancel_policy"),
        "partial_failure_policy": metadata.get("partial_failure_policy"),
        "artifact_output_ref": metadata.get("artifact_output_ref"),
        "progress_summary": _batch_progress_summary_payload(metadata),
        "items": metadata.get("items") or [],
        "tenant_id": record.tenant_id,
        "project_id": record.project_id,
        "environment": metadata.get("environment"),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _batch_progress_summary_payload(metadata: dict[str, Any]) -> dict[str, int]:
    progress_summary = dict(metadata.get("progress_summary") or {})
    return {
        "total_items": int(progress_summary.get("total_items") or 0),
        "queued_items": int(progress_summary.get("queued_items") or 0),
        "running_items": int(progress_summary.get("running_items") or 0),
        "retrying_items": int(progress_summary.get("retrying_items") or 0),
        "failed_items": int(progress_summary.get("failed_items") or 0),
        "dead_letter_items": int(progress_summary.get("dead_letter_items") or 0),
        "cancelled_items": int(progress_summary.get("cancelled_items") or 0),
        "completed_items": int(progress_summary.get("completed_items") or 0),
        "terminal_items": int(progress_summary.get("terminal_items") or 0),
    }


def _refresh_batch_record(
    record: BatchRuns,
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    tenant_id: int,
    project_id: int,
) -> None:
    metadata = dict(record.metadata_json or {})
    items = list(metadata.get("items") or [])
    changed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        task_id = item.get("task_id")
        if not isinstance(task_id, int):
            continue
        task = runtime.get_task(task_id, tenant_id=tenant_id, project_id=project_id)
        if task is None:
            continue
        next_status = task.status.value
        if str(item.get("status") or "") != next_status:
            item["status"] = next_status
            changed = True
        if task.dead_letter_reason and not item.get("message"):
            item["message"] = task.dead_letter_reason
            changed = True
    summary = summarize_batch_items(items)
    next_status = overall_batch_status(summary)
    next_summary = {
        "total_items": summary.total_items,
        "queued_items": summary.queued_items,
        "running_items": summary.running_items,
        "retrying_items": summary.retrying_items,
        "failed_items": summary.failed_items,
        "dead_letter_items": summary.dead_letter_items,
        "cancelled_items": summary.cancelled_items,
        "completed_items": summary.completed_items,
        "terminal_items": summary.terminal_items,
    }
    if metadata.get("items") != items:
        metadata["items"] = items
        changed = True
    if metadata.get("progress_summary") != next_summary:
        metadata["progress_summary"] = next_summary
        changed = True
    metadata["last_updated_at"] = datetime.now(UTC).isoformat()
    if summary.terminal_items == summary.total_items and summary.total_items > 0:
        metadata["completed_at"] = metadata.get("completed_at") or datetime.now(UTC).isoformat()
    if record.status != next_status:
        record.status = next_status
        changed = True
    if changed:
        record.metadata_json = metadata


@router.post("/v1/batch-runs", status_code=status.HTTP_201_CREATED)
def create_batch_run(
    runtime: NativeRuntimeDep,
    service: DeploymentControlDep,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    try:
        normalized = normalize_batch_payload(payload or {})
        accepted_items, failed_items = normalize_batch_items(
            list(normalized["input_items"]),
            partial_failure_policy=normalized["partial_failure_policy"],
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": str(exc),
                "message": "Batch payload is invalid.",
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
                "message": "Batch deployment binding was not found in scope.",
                "request_id": x_request_id,
            },
        )
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
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "batch_binding_invalid",
                "message": "Batch binding no longer resolves to an active agent version.",
                "request_id": x_request_id,
            },
        )
    created_items: list[dict[str, Any]] = list(failed_items)
    for index, item in enumerate(accepted_items):
        run, task, _ = runtime.create_task_run(
            tenant_id=tenant_id,
            project_id=project_id,
            agent=agent,
            agent_version=agent_version,
            input_data=item,
            thread_id=None,
            idempotency_key=None,
            endpoint="/v1/batch-runs",
            request_body={
                "batch_name": normalized["name"],
                "index": index,
                "input": item,
                "audit_reason": normalized["audit_reason"],
            },
            deployment_id=deployment.id,
        )
        created_items.append(
            {
                "index": index,
                "status": "queued",
                "input": item,
                "run_id": run.id,
                "task_id": task.id,
            }
        )
    created_items.sort(key=lambda item: int(item["index"]))
    summary = summarize_batch_items(created_items)
    session = _session_for_runtime(runtime)
    should_close_session = not isinstance(runtime, SQLAlchemyNativeRuntimeStore)
    try:
        metadata = {
            **normalized,
            "environment": x_environment,
            "agent_id": deployment.agent_id,
            "agent_version_id": deployment.agent_version_id,
            "items": created_items,
            "progress_summary": {
                "total_items": summary.total_items,
                "queued_items": summary.queued_items,
                "running_items": summary.running_items,
                "retrying_items": summary.retrying_items,
                "failed_items": summary.failed_items,
                "dead_letter_items": summary.dead_letter_items,
                "cancelled_items": summary.cancelled_items,
                "completed_items": summary.completed_items,
                "terminal_items": summary.terminal_items,
            },
            "last_updated_at": datetime.now(UTC).isoformat(),
        }
        record = BatchRuns(
            tenant_id=tenant_id,
            project_id=project_id,
            status=overall_batch_status(summary),
            metadata_json=metadata,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return {"item": _batch_item(record), "request_id": x_request_id}
    finally:
        if should_close_session:
            session.close()


@router.get("/v1/batch-runs")
def list_batch_runs(
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
            session.query(BatchRuns)
            .filter(
                BatchRuns.is_deleted.is_(False),
                BatchRuns.tenant_id == tenant_id,
                BatchRuns.project_id == project_id,
            )
            .order_by(BatchRuns.id.asc())
            .all()
        )
        for record in records:
            _refresh_batch_record(
                record,
                runtime=runtime,
                tenant_id=tenant_id,
                project_id=project_id,
            )
        session.commit()
        items = [_batch_item(record) for record in records]
        return {"items": items, "count": len(items), "request_id": x_request_id}
    finally:
        session.close()


@router.get("/v1/batch-runs/{batch_id}")
def get_batch_run(
    batch_id: int,
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
        record = session.get(BatchRuns, batch_id)
        if (
            record is None
            or record.is_deleted
            or record.tenant_id != tenant_id
            or record.project_id != project_id
        ):
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "batch_run_not_found",
                    "message": "Batch run was not found.",
                    "request_id": x_request_id,
                },
            )
        _refresh_batch_record(
            record,
            runtime=runtime,
            tenant_id=tenant_id,
            project_id=project_id,
        )
        session.commit()
        return {"item": _batch_item(record), "request_id": x_request_id}
    finally:
        session.close()


@router.post("/v1/batch-runs/{batch_id}/cancel")
def cancel_batch_run(
    batch_id: int,
    runtime: NativeRuntimeDep,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
) -> Any:
    reason = str((payload or {}).get("audit_reason") or "").strip()
    if not reason:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "audit_reason_required",
                "message": "Batch cancellation requires an audit_reason.",
                "request_id": x_request_id,
            },
        )
    scope = _require_scope(x_tenant_id, x_project_id)
    if isinstance(scope, JSONResponse):
        return scope
    tenant_id, project_id = scope
    session = _session_for_runtime(runtime)
    should_close_session = not isinstance(runtime, SQLAlchemyNativeRuntimeStore)
    try:
        record = session.get(BatchRuns, batch_id)
        if (
            record is None
            or record.is_deleted
            or record.tenant_id != tenant_id
            or record.project_id != project_id
        ):
            return JSONResponse(
                status_code=404,
                content={
                    "error_code": "batch_run_not_found",
                    "message": "Batch run was not found.",
                    "request_id": x_request_id,
                },
            )
        metadata = dict(record.metadata_json or {})
        items = list(metadata.get("items") or [])
        task_map = {
            task.id: task
            for task in runtime.list_tasks(
                tenant_id=tenant_id,
                project_id=project_id,
            )
        }
        for item in items:
            task_id = item.get("task_id")
            task = task_map.get(int(task_id)) if isinstance(task_id, int) else None
            if task is not None and task.status in {
                TaskStatus.queued,
                TaskStatus.leased,
                TaskStatus.running,
            }:
                runtime.cancel_task(task)
                item["status"] = "cancelled"
            elif item.get("status") == "queued":
                item["status"] = "cancelled"
        summary = summarize_batch_items(items)
        metadata["items"] = items
        metadata["progress_summary"] = {
            "total_items": summary.total_items,
            "queued_items": summary.queued_items,
            "running_items": summary.running_items,
            "retrying_items": summary.retrying_items,
            "failed_items": summary.failed_items,
            "dead_letter_items": summary.dead_letter_items,
            "cancelled_items": summary.cancelled_items,
            "completed_items": summary.completed_items,
            "terminal_items": summary.terminal_items,
        }
        metadata["cancelled_at"] = datetime.now(UTC).isoformat()
        metadata["cancel_audit_reason"] = reason
        record.status = overall_batch_status(summary)
        record.metadata_json = metadata
        session.commit()
        session.refresh(record)
        return {"item": _batch_item(record), "request_id": x_request_id}
    finally:
        if should_close_session:
            session.close()
