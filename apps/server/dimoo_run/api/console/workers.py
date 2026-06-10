from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from dimoo_run.api.console.common import (
    AuditReasonHeader,
    AuthorizationHeader,
    DeploymentControlDep,
    EnvironmentHeader,
    NativeRuntimeDep,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    console_read_actor,
)
from dimoo_run.api.console.schemas import (
    ConsoleCapacitySummary,
    ConsoleControlAction,
    ConsoleQueuePressure,
    ConsoleWorkerDetail,
    ConsoleWorkerHealth,
)
from dimoo_run.runtime.capacity import (
    build_capacity_summary,
    build_worker_actions,
    build_worker_detail_view,
    build_worker_health_views,
    default_worker_registry,
)

router = APIRouter(prefix="/v1/console", tags=["console-runtime-workers"])


@router.get("/workers", response_model=None)
def list_workers(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
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
    items = [
        ConsoleWorkerHealth.model_validate(item).model_dump(mode="json")
        for item in build_worker_health_views(
            runtime=runtime,
            deployments=deployments,
            workers=default_worker_registry(),
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    ]
    return {"items": items, "count": len(items), "request_id": x_request_id}


@router.get("/workers/{worker_id}", response_model=None)
def get_worker(
    worker_id: str,
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
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
    try:
        detail = build_worker_detail_view(
            worker_id=worker_id,
            runtime=runtime,
            deployments=deployments,
            workers=default_worker_registry(),
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    except KeyError:
        return _not_found(worker_id, x_request_id)
    tasks = detail["scoped_tasks"]
    registry = default_worker_registry()
    worker = registry.get(
        worker_id,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    if worker is None:
        worker = registry.ensure(
            worker_id=worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
            status=str(detail["status"]),
            version=str(detail["version"]),
            capacity=max(1, int(detail["capacity"])),
        )
    detail["actions"] = [
        ConsoleControlAction.model_validate(action).model_dump(mode="json")
        for action in build_worker_actions(
            worker=worker,
            tasks=tasks,
            actor_scopes=actor.scopes,
        )
    ]
    return {
        "item": ConsoleWorkerDetail.model_validate(
            {key: value for key, value in detail.items() if key != "scoped_tasks"}
        ).model_dump(mode="json"),
        "request_id": x_request_id,
    }


@router.post("/workers/{worker_id}/{action}", response_model=None)
def control_worker(
    worker_id: str,
    action: str,
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
    x_audit_reason: AuditReasonHeader = None,
) -> dict[str, Any] | JSONResponse:
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
    if "*" not in actor.scopes and "agent:deploy" not in actor.scopes:
        return JSONResponse(
            status_code=403,
            content={
                "error_code": "api_key_scope_denied",
                "message": "Current actor lacks agent:deploy permission.",
                "request_id": x_request_id,
                "details": {"required_scope": "agent:deploy"},
            },
        )
    registry = default_worker_registry()
    worker = registry.get(
        worker_id,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    if worker is None or worker.tenant_id != tenant_id or worker.project_id != project_id:
        return _not_found(worker_id, x_request_id)
    tasks = build_worker_detail_view(
        worker_id=worker_id,
        runtime=runtime,
        deployments=deployments,
        workers=registry,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )["scoped_tasks"]
    actions = {
        item["action"]: item
        for item in build_worker_actions(
            worker=worker,
            tasks=tasks,
            actor_scopes=actor.scopes,
        )
    }
    current = actions.get(action)
    if current is None:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "worker_action_not_found",
                "message": "Worker action was not found.",
                "request_id": x_request_id,
                "details": {"worker_id": worker_id, "action": action},
            },
        )
    if not current["available"]:
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "worker_action_blocked",
                "message": current["disabled_reasons"][0],
                "request_id": x_request_id,
                "details": {
                    "worker_id": worker_id,
                    "action": action,
                    "disabled_reasons": current["disabled_reasons"],
                },
            },
        )
    if action == "drain":
        registry.drain(
            worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    elif action == "undrain":
        registry.undrain(
            worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    elif action == "quarantine":
        registry.quarantine(
            worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    elif action == "restart-request":
        registry.request_restart(
            worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
    else:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "worker_action_not_found",
                "message": "Worker action was not found.",
                "request_id": x_request_id,
                "details": {"worker_id": worker_id, "action": action},
            },
        )
    detail = build_worker_detail_view(
        worker_id=worker_id,
        runtime=runtime,
        deployments=deployments,
        workers=registry,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    updated_worker = registry.get(
        worker_id,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    if updated_worker is None:
        return _not_found(worker_id, x_request_id)
    detail["actions"] = [
        ConsoleControlAction.model_validate(item).model_dump(mode="json")
        for item in build_worker_actions(
            worker=updated_worker,
            tasks=tasks,
            actor_scopes=actor.scopes,
        )
    ]
    _write_worker_audit(
        deployments=deployments,
        worker=updated_worker,
        worker_id=worker_id,
        actor_id=actor.actor_id,
        tenant_id=tenant_id,
        project_id=project_id,
        request_id=x_request_id,
        action=action,
        audit_reason=x_audit_reason,
    )
    return {
        "item": ConsoleWorkerDetail.model_validate(
            {key: value for key, value in detail.items() if key != "scoped_tasks"}
        ).model_dump(mode="json"),
        "request_id": x_request_id,
    }


@router.get("/capacity", response_model=None)
def get_capacity_summary(
    runtime: NativeRuntimeDep,
    deployments: DeploymentControlDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
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
    summary = build_capacity_summary(
        runtime=runtime,
        deployments=deployments,
        workers=default_worker_registry(),
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    summary["queues"] = [
        ConsoleQueuePressure.model_validate(item).model_dump(mode="json")
        for item in summary["queues"]
    ]
    return {
        "item": ConsoleCapacitySummary.model_validate(summary).model_dump(mode="json"),
        "request_id": x_request_id,
    }


def _write_worker_audit(
    *,
    deployments: DeploymentControlDep,
    worker: object,
    worker_id: str,
    actor_id: str,
    tenant_id: int,
    project_id: int,
    request_id: str | None,
    action: str,
    audit_reason: str | None,
) -> None:
    from dimoo_run.deployments.service import AuditEntry

    deployments.audit_sink.write(
        AuditEntry(
            action=f"worker.{action}",
            resource_type="worker",
            resource_id=int(getattr(worker, "id", 0) or 0),
            actor_id=actor_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=request_id,
            result="allowed",
            metadata={
                "worker_id": worker_id,
                "audit_reason": audit_reason or "",
            },
        )
    )


def _not_found(worker_id: str, request_id: str | None) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error_code": "worker_not_found",
            "message": "Worker was not found.",
            "request_id": request_id,
            "details": {"worker_id": worker_id},
        },
    )
