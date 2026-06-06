from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dimoo_run.api.dependencies import (
    AuthorizationHeader,
    IdempotencyKeyHeader,
    RequestIdHeader,
    authenticate_api_key,
)
from dimoo_run.api.native.dependencies import get_native_runtime
from dimoo_run.api.native.deployments import (
    DeploymentControlDep,
    deployment_in_scope,
    deployment_not_found,
    deployment_to_read,
    error_response,
    require_scope,
)
from dimoo_run.api.native.runtime import NativeRuntimeStore, SQLAlchemyNativeRuntimeStore
from dimoo_run.deployments.service import (
    AuditEntry,
    DeploymentNotFoundError,
    DeploymentRecord,
    PolicyDeniedError,
)
from dimoo_run.domain.enums import RunStatus, TaskStatus
from dimoo_run.domain.schemas import DeploymentRead, ErrorResponse

router = APIRouter(tags=["native-deployment-promotion"])
TenantIdHeader = Annotated[int | None, Header(alias="X-Tenant-Id")]
ProjectIdHeader = Annotated[int | None, Header(alias="X-Project-Id")]
NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]


class DeploymentPromotionPreviewRead(BaseModel):
    deployment_id: int
    environment: str
    desired_status: str
    runtime_status: str
    current_agent_version_id: int
    candidate_agent_version_id: int
    active_runs: int
    queued_tasks: int
    candidate_validation_status: str
    rollback_agent_version_id: int | None
    required_permissions: list[str]
    audit_required: bool
    can_promote: bool
    blocked_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class DeploymentPromotePayload(BaseModel):
    candidate_version_id: int
    expected_current_version_id: int
    rollout_reason: str = Field(min_length=1)


class DeploymentRollbackPayload(BaseModel):
    expected_current_version_id: int
    rollback_agent_version_id: int | None = None
    rollback_reason: str = Field(min_length=1)


@router.get(
    "/deployments/{deployment_id}/promotion-preview",
    response_model=DeploymentPromotionPreviewRead,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def preview_deployment_promotion(
    deployment_id: int,
    candidate_version_id: Annotated[int, Query()],
    service: DeploymentControlDep,
    runtime: NativeRuntimeDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentPromotionPreviewRead | JSONResponse:
    auth = _authorize(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:read",
    )
    if isinstance(auth, JSONResponse):
        return auth
    deployment = _get_scoped_deployment(
        service=service,
        deployment_id=deployment_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if isinstance(deployment, JSONResponse):
        return deployment
    return _promotion_preview(
        deployment=deployment,
        candidate_version_id=candidate_version_id,
        runtime=runtime,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
    )


@router.post(
    "/deployments/{deployment_id}/promote",
    response_model=DeploymentRead,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def promote_deployment(
    deployment_id: int,
    payload: DeploymentPromotePayload,
    service: DeploymentControlDep,
    runtime: NativeRuntimeDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    authorization: AuthorizationHeader = None,
    idempotency_key: IdempotencyKeyHeader = None,
) -> DeploymentRead | JSONResponse:
    auth = _authorize(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:deploy",
    )
    if isinstance(auth, JSONResponse):
        return auth
    deployment = _get_scoped_deployment(
        service=service,
        deployment_id=deployment_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if isinstance(deployment, JSONResponse):
        return deployment
    conflict = _expected_version_conflict(
        deployment=deployment,
        expected_current_version_id=payload.expected_current_version_id,
        request_id=x_request_id,
    )
    if conflict is not None:
        return conflict
    candidate_error = _candidate_version_error(
        deployment=deployment,
        candidate_version_id=payload.candidate_version_id,
        runtime=runtime,
        request_id=x_request_id,
    )
    if candidate_error is not None:
        return candidate_error
    policy_error = _policy_error(
        service=service,
        deployment=deployment,
        action="deployment.promote",
        actor_id=auth.actor_id,
        request_id=x_request_id,
    )
    if policy_error is not None:
        return policy_error

    previous_version_id = deployment.agent_version_id
    deployment.agent_version_id = payload.candidate_version_id
    deployment.config_json = {
        **deployment.config_json,
        "promotion": {
            "previous_agent_version_id": previous_version_id,
            "current_agent_version_id": payload.candidate_version_id,
            "rollout_reason": payload.rollout_reason,
            "idempotency_key": idempotency_key,
        },
    }
    updated = service.deployments.save(deployment)
    _write_audit(
        service=service,
        deployment=deployment,
        action="deployment.promote",
        actor_id=auth.actor_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        metadata={
            "previous_agent_version_id": str(previous_version_id),
            "candidate_agent_version_id": str(payload.candidate_version_id),
            "rollout_reason": payload.rollout_reason,
            "idempotency_key": idempotency_key or "",
        },
    )
    return deployment_to_read(updated)


@router.post(
    "/deployments/{deployment_id}/rollback",
    response_model=DeploymentRead,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def rollback_deployment(
    deployment_id: int,
    payload: DeploymentRollbackPayload,
    service: DeploymentControlDep,
    runtime: NativeRuntimeDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    authorization: AuthorizationHeader = None,
    idempotency_key: IdempotencyKeyHeader = None,
) -> DeploymentRead | JSONResponse:
    auth = _authorize(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:deploy",
    )
    if isinstance(auth, JSONResponse):
        return auth
    deployment = _get_scoped_deployment(
        service=service,
        deployment_id=deployment_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if isinstance(deployment, JSONResponse):
        return deployment
    conflict = _expected_version_conflict(
        deployment=deployment,
        expected_current_version_id=payload.expected_current_version_id,
        request_id=x_request_id,
    )
    if conflict is not None:
        return conflict
    rollback_version_id = payload.rollback_agent_version_id or _rollback_version_id(deployment)
    if rollback_version_id is None:
        return error_response(
            status_code=409,
            error_code="deployment_rollback_unavailable",
            message="Deployment has no previous promoted version to roll back to.",
            request_id=x_request_id,
            details={"deployment_id": deployment.id},
        )
    candidate_error = _candidate_version_error(
        deployment=deployment,
        candidate_version_id=rollback_version_id,
        runtime=runtime,
        request_id=x_request_id,
    )
    if candidate_error is not None:
        return candidate_error
    policy_error = _policy_error(
        service=service,
        deployment=deployment,
        action="deployment.rollback",
        actor_id=auth.actor_id,
        request_id=x_request_id,
    )
    if policy_error is not None:
        return policy_error

    replaced_version_id = deployment.agent_version_id
    deployment.agent_version_id = rollback_version_id
    deployment.config_json = {
        **deployment.config_json,
        "promotion": {
            **_promotion_config(deployment),
            "previous_agent_version_id": replaced_version_id,
            "current_agent_version_id": rollback_version_id,
            "rollback_reason": payload.rollback_reason,
            "idempotency_key": idempotency_key,
        },
    }
    updated = service.deployments.save(deployment)
    _write_audit(
        service=service,
        deployment=deployment,
        action="deployment.rollback",
        actor_id=auth.actor_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        metadata={
            "previous_agent_version_id": str(replaced_version_id),
            "rollback_agent_version_id": str(rollback_version_id),
            "rollback_reason": payload.rollback_reason,
            "idempotency_key": idempotency_key or "",
        },
    )
    return deployment_to_read(updated)


def _authorize(
    *,
    authorization: str | None,
    tenant_id: int | None,
    project_id: int | None,
    request_id: str | None,
    required_scope: str,
) -> Any | JSONResponse:
    scope_error = require_scope(
        tenant_id=tenant_id,
        project_id=project_id,
        request_id=request_id,
    )
    if scope_error is not None:
        return scope_error
    assert tenant_id is not None
    assert project_id is not None
    return authenticate_api_key(
        authorization=authorization,
        tenant_id=tenant_id,
        project_id=project_id,
        required_scope=required_scope,
        request_id=request_id,
    )


def _get_scoped_deployment(
    *,
    service: Any,
    deployment_id: int,
    tenant_id: int | None,
    project_id: int | None,
    request_id: str | None,
) -> DeploymentRecord | JSONResponse:
    try:
        deployment = cast(DeploymentRecord, service.deployments.get(deployment_id))
    except DeploymentNotFoundError:
        return deployment_not_found(deployment_id, request_id)
    if not deployment_in_scope(deployment, tenant_id=tenant_id, project_id=project_id):
        return deployment_not_found(deployment_id, request_id)
    return deployment


def _promotion_preview(
    *,
    deployment: DeploymentRecord,
    candidate_version_id: int,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    tenant_id: int | None,
    project_id: int | None,
) -> DeploymentPromotionPreviewRead:
    candidate = runtime.get_version_by_id(deployment.agent_id, candidate_version_id)
    candidate_status = candidate.status if candidate is not None else "missing"
    blocked_reason = None
    if candidate is None:
        blocked_reason = "candidate_version_not_found"
    elif candidate.status != "ready":
        blocked_reason = "candidate_version_not_ready"
    active_runs, queued_tasks = _runtime_pressure(
        runtime=runtime,
        deployment_id=deployment.id,
        tenant_id=tenant_id,
        project_id=project_id,
    )
    warnings = []
    if active_runs > 0:
        warnings.append("active_runs_will_continue_on_current_version")
    if queued_tasks > 0:
        warnings.append("queued_tasks_will_use_current_version")
    return DeploymentPromotionPreviewRead(
        deployment_id=deployment.id,
        environment=deployment.environment,
        desired_status=deployment.desired_status.value,
        runtime_status=deployment.runtime_status.value,
        current_agent_version_id=deployment.agent_version_id,
        candidate_agent_version_id=candidate_version_id,
        active_runs=active_runs,
        queued_tasks=queued_tasks,
        candidate_validation_status=candidate_status,
        rollback_agent_version_id=_rollback_version_id(deployment) or deployment.agent_version_id,
        required_permissions=["agent:deploy"],
        audit_required=True,
        can_promote=blocked_reason is None,
        blocked_reason=blocked_reason,
        warnings=warnings,
    )


def _runtime_pressure(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployment_id: int,
    tenant_id: int | None,
    project_id: int | None,
) -> tuple[int, int]:
    if tenant_id is None or project_id is None:
        return 0, 0
    deployment_runs = [
        run
        for run in runtime.list_runs(tenant_id=tenant_id, project_id=project_id)
        if run.deployment_id == deployment_id
    ]
    active_run_ids = {
        run.id
        for run in deployment_runs
        if run.status in {RunStatus.pending, RunStatus.running, RunStatus.interrupted}
    }
    deployment_run_ids = {run.id for run in deployment_runs}
    queued_tasks = sum(
        1
        for task in runtime.list_tasks(tenant_id=tenant_id, project_id=project_id)
        if task.run_id in deployment_run_ids and task.status == TaskStatus.queued
    )
    return len(active_run_ids), queued_tasks


def _expected_version_conflict(
    *,
    deployment: DeploymentRecord,
    expected_current_version_id: int,
    request_id: str | None,
) -> JSONResponse | None:
    if deployment.agent_version_id == expected_current_version_id:
        return None
    return error_response(
        status_code=409,
        error_code="deployment_version_conflict",
        message="Deployment version changed after the promotion workflow was prepared.",
        request_id=request_id,
        details={
            "deployment_id": deployment.id,
            "expected_current_version_id": expected_current_version_id,
            "actual_current_version_id": deployment.agent_version_id,
        },
    )


def _candidate_version_error(
    *,
    deployment: DeploymentRecord,
    candidate_version_id: int,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    request_id: str | None,
) -> JSONResponse | None:
    candidate = runtime.get_version_by_id(deployment.agent_id, candidate_version_id)
    if candidate is None:
        return error_response(
            status_code=404,
            error_code="agent_version_not_found",
            message="Candidate agent version was not found.",
            request_id=request_id,
            details={
                "agent_id": deployment.agent_id,
                "agent_version_id": candidate_version_id,
            },
        )
    if candidate.status != "ready":
        return error_response(
            status_code=409,
            error_code="agent_version_not_ready",
            message="Candidate agent version must be ready before promotion.",
            request_id=request_id,
            details={
                "agent_id": deployment.agent_id,
                "agent_version_id": candidate_version_id,
                "status": candidate.status,
            },
        )
    return None


def _policy_error(
    *,
    service: Any,
    deployment: DeploymentRecord,
    action: str,
    actor_id: str | None,
    request_id: str | None,
) -> JSONResponse | None:
    decision = service.policy_engine.evaluate(
        actor_id=actor_id,
        action=action,
        deployment=deployment,
    )
    if decision.allowed:
        return None
    _write_audit(
        service=service,
        deployment=deployment,
        action=action,
        actor_id=actor_id,
        tenant_id=deployment.tenant_id,
        project_id=deployment.project_id,
        request_id=request_id,
        result="denied",
        metadata={"reason": decision.reason or "policy_denied"},
    )
    exc = PolicyDeniedError(decision.reason or "policy_denied")
    return error_response(
        status_code=403,
        error_code=exc.error_code,
        message=exc.reason,
        request_id=request_id,
        details={"deployment_id": deployment.id},
    )


def _write_audit(
    *,
    service: Any,
    deployment: DeploymentRecord,
    action: str,
    actor_id: str | None,
    tenant_id: int | None,
    project_id: int | None,
    request_id: str | None,
    result: str = "allowed",
    metadata: dict[str, str],
) -> None:
    service.audit_sink.write(
        AuditEntry(
            action=action,
            resource_type="deployment",
            resource_id=deployment.id,
            actor_id=actor_id,
            tenant_id=tenant_id,
            project_id=project_id,
            request_id=request_id,
            result=result,
            metadata=metadata,
        )
    )


def _promotion_config(deployment: DeploymentRecord) -> dict[str, Any]:
    promotion = deployment.config_json.get("promotion")
    return promotion if isinstance(promotion, dict) else {}


def _rollback_version_id(deployment: DeploymentRecord) -> int | None:
    previous = _promotion_config(deployment).get("previous_agent_version_id")
    return previous if isinstance(previous, int) else None
