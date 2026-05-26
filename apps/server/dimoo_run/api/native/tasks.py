from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dimoo_run.api.compat.auth import ProjectIdHeader, TenantIdHeader
from dimoo_run.api.dependencies import (
    AuthorizationHeader,
    RequestIdHeader,
    authenticate_api_key,
    error_response,
)
from dimoo_run.api.native.dependencies import get_native_runtime
from dimoo_run.api.native.runtime import (
    NativeRuntimeStore,
    NativeTask,
    SQLAlchemyNativeRuntimeStore,
)

router = APIRouter(tags=["native-tasks"])
NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]


class TaskRead(BaseModel):
    id: str
    run_id: str
    tenant_id: str
    project_id: str
    status: str
    queue: str
    priority: int
    attempt: int
    max_attempts: int
    idempotency_key: str | None = None
    error: dict[str, str] | None = None
    dead_letter_reason: str | None = None


def _task_to_read(task: NativeTask) -> TaskRead:
    payload = task.__dict__.copy()
    payload["status"] = task.status.value
    return TaskRead.model_validate(payload)


def _find_task(
    task_id: str,
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    authorization: str | None,
    tenant_id: str | None,
    project_id: str | None,
    request_id: str | None,
    required_scope: str = "agent:read",
) -> NativeTask | JSONResponse:
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
    task = runtime.get_task(task_id, tenant_id=tenant_id, project_id=project_id)
    if task is None:
        return error_response(
            status_code=404,
            error_code="task_not_found",
            message="Task was not found.",
            request_id=request_id,
            details={"task_id": task_id},
        )
    return task


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(
    task_id: str,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> TaskRead | JSONResponse:
    task = _find_task(
        task_id,
        runtime=runtime,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if isinstance(task, JSONResponse):
        return task
    return _task_to_read(task)


@router.post("/tasks/{task_id}/cancel", response_model=TaskRead)
def cancel_task(
    task_id: str,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> TaskRead | JSONResponse:
    task = _find_task(
        task_id,
        runtime=runtime,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:invoke",
    )
    if isinstance(task, JSONResponse):
        return task
    cancelled = runtime.cancel_task(task)
    return _task_to_read(cancelled)
