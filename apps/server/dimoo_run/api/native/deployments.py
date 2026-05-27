from collections.abc import Callable, Generator
from functools import lru_cache
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from dimoo_run.api.dependencies import AuthorizationHeader, RequestIdHeader, authenticate_api_key
from dimoo_run.api.native.dependencies import get_native_runtime
from dimoo_run.api.native.runtime import (
    NativeRuntimeStore,
    SQLAlchemyNativeRuntimeStore,
)
from dimoo_run.core.config import Settings
from dimoo_run.deployments.service import (
    AuditEntry,
    DeploymentNotFoundError,
    DeploymentRecord,
    DeploymentRuntimeControlService,
    PolicyDeniedError,
)
from dimoo_run.domain.enums import DeploymentDesiredStatus, DeploymentRuntimeStatus
from dimoo_run.domain.models import Deployment
from dimoo_run.domain.schemas import AgentInstanceRead, DeploymentRead, ErrorResponse
from dimoo_run.persistence.database import create_session_factory
from dimoo_run.persistence.repositories import AuditLogRepository, DeploymentRepository

router = APIRouter(tags=["native-deployments"])
ActorIdHeader = Annotated[str | None, Header(alias="X-Actor-Id")]
TenantIdHeader = Annotated[str | None, Header(alias="X-Tenant-Id")]
ProjectIdHeader = Annotated[str | None, Header(alias="X-Project-Id")]

_default_deployment_control = DeploymentRuntimeControlService()


class SQLAlchemyDeploymentStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, deployment: DeploymentRecord) -> DeploymentRecord:
        model = DeploymentRepository(self.session).create(
            Deployment(
                id=deployment.id,
                tenant_id=deployment.tenant_id,
                project_id=deployment.project_id,
                agent_id=deployment.agent_id,
                agent_version_id=deployment.agent_version_id,
                environment=deployment.environment,
                desired_status=deployment.desired_status.value,
                runtime_status=deployment.runtime_status.value,
                replicas=deployment.replicas,
                config_json=deployment.config_json,
                last_runtime_error=deployment.last_runtime_error,
            )
        )
        self.session.flush()
        return deployment_from_model(model)

    def get(self, deployment_id: str) -> DeploymentRecord:
        deployment = DeploymentRepository(self.session).get_by_id(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError(deployment_id)
        return deployment_from_model(deployment)

    def list(
        self,
        *,
        tenant_id: str | None = None,
        project_id: str | None = None,
    ) -> list[DeploymentRecord]:
        conditions: list[Any] = [Deployment.is_deleted.is_(False)]
        if tenant_id is not None:
            conditions.append(Deployment.tenant_id == tenant_id)
        if project_id is not None:
            conditions.append(Deployment.project_id == project_id)
        statement = select(Deployment).where(*conditions)
        return [
            deployment_from_model(deployment)
            for deployment in self.session.scalars(statement)
        ]

    def save(self, deployment: DeploymentRecord) -> DeploymentRecord:
        model = DeploymentRepository(self.session).transition(
            deployment.id,
            desired_status=deployment.desired_status.value,
            runtime_status=deployment.runtime_status.value,
            last_runtime_error=deployment.last_runtime_error,
        )
        model.replicas = deployment.replicas
        model.config_json = deployment.config_json
        self.session.flush()
        return deployment_from_model(model)


class SQLAlchemyAuditSink:
    def __init__(self, session: Session) -> None:
        self.session = session

    def write(self, entry: AuditEntry) -> None:
        if entry.tenant_id is None:
            return
        AuditLogRepository(self.session).append(
            audit_id=f"audit_{uuid4().hex[:12]}",
            tenant_id=entry.tenant_id,
            project_id=entry.project_id,
            actor_id=entry.actor_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            result=entry.result,
            request_id=entry.request_id,
            metadata=entry.metadata,
        )
        self.session.flush()


@lru_cache(maxsize=4)
def _deployment_session_factory(database_url: str) -> sessionmaker[Session]:
    return create_session_factory(database_url)


def default_deployment_control() -> DeploymentRuntimeControlService:
    return _default_deployment_control


def reset_deployment_control() -> None:
    global _default_deployment_control
    _default_deployment_control = DeploymentRuntimeControlService()


def get_deployment_control() -> Generator[DeploymentRuntimeControlService, None, None]:
    settings = Settings.from_env()
    if settings.runtime.native_runtime_store != "sqlalchemy":
        yield _default_deployment_control
        return

    session_factory = _deployment_session_factory(settings.database.url)
    session = session_factory()
    try:
        yield DeploymentRuntimeControlService(
            deployments=SQLAlchemyDeploymentStore(session),  # type: ignore[arg-type]
            audit_sink=SQLAlchemyAuditSink(session),  # type: ignore[arg-type]
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DeploymentControlDep = Annotated[
    DeploymentRuntimeControlService,
    Depends(get_deployment_control),
]
NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]
CONTROL_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


class DeploymentCreate(BaseModel):
    agent_id: str
    agent_version_id: str
    environment: str = Field(min_length=1)
    desired_status: DeploymentDesiredStatus = DeploymentDesiredStatus.draft
    replicas: int = Field(default=1, ge=1)
    config: dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/deployments",
    response_model=DeploymentRead,
    status_code=201,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_deployment(
    payload: DeploymentCreate,
    service: DeploymentControlDep,
    runtime: NativeRuntimeDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    scope_error = require_scope(
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if scope_error is not None:
        return scope_error
    assert x_tenant_id is not None
    assert x_project_id is not None
    auth = authenticate_api_key(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:deploy",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    agent = runtime.get_agent(payload.agent_id, tenant_id=x_tenant_id, project_id=x_project_id)
    if agent is None:
        return error_response(
            status_code=404,
            error_code="agent_not_found",
            message="Agent was not found.",
            request_id=x_request_id,
            details={"agent_id": payload.agent_id},
        )
    agent_version = runtime.get_version_by_id(payload.agent_id, payload.agent_version_id)
    if agent_version is None:
        return error_response(
            status_code=404,
            error_code="agent_version_not_found",
            message="Agent version was not found.",
            request_id=x_request_id,
            details={
                "agent_id": payload.agent_id,
                "agent_version_id": payload.agent_version_id,
            },
        )
    for deployment in service.deployments.list(tenant_id=x_tenant_id, project_id=x_project_id):
        if (
            deployment.environment == payload.environment
            and deployment.agent_id == payload.agent_id
        ):
            return error_response(
                status_code=409,
                error_code="deployment_already_exists",
                message="Deployment already exists for this agent and environment.",
                request_id=x_request_id,
                details={
                    "agent_id": payload.agent_id,
                    "environment": payload.environment,
                },
            )
    deployment = service.deployments.add(
        DeploymentRecord(
            id=f"deployment_{uuid4().hex[:12]}",
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            agent_id=payload.agent_id,
            agent_version_id=payload.agent_version_id,
            environment=payload.environment,
            desired_status=payload.desired_status,
            runtime_status=(
                DeploymentRuntimeStatus.stopped
                if payload.desired_status == DeploymentDesiredStatus.stopped
                else DeploymentRuntimeStatus.not_loaded
            ),
            replicas=payload.replicas,
            config_json=payload.config,
        )
    )
    service.audit_sink.write(
        AuditEntry(
            action="deployment.create",
            resource_type="deployment",
            resource_id=deployment.id,
            actor_id=auth.actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
            result="allowed",
            metadata={
                "agent_id": payload.agent_id,
                "agent_version_id": payload.agent_version_id,
                "environment": payload.environment,
            },
        )
    )
    return deployment_to_read(deployment)


@router.get(
    "/deployments",
    response_model=list[DeploymentRead],
    responses={400: {"model": ErrorResponse}},
)
def list_deployments(
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> list[DeploymentRead] | JSONResponse:
    scope_error = require_scope(
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if scope_error is not None:
        return scope_error
    assert x_tenant_id is not None
    auth = authenticate_api_key(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:read",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    return [
        deployment_to_read(deployment)
        for deployment in service.deployments.list(
            tenant_id=x_tenant_id,
            project_id=x_project_id,
        )
    ]


@router.get(
    "/deployments/{deployment_id}",
    response_model=DeploymentRead,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    scope_error = require_scope(
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if scope_error is not None:
        return scope_error
    assert x_tenant_id is not None
    auth = authenticate_api_key(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:read",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    try:
        deployment = service.deployments.get(deployment_id)
    except DeploymentNotFoundError:
        return error_response(
            status_code=404,
            error_code="deployment_not_found",
            message="Deployment was not found.",
            request_id=x_request_id,
            details={"deployment_id": deployment_id},
        )
    if not deployment_in_scope(deployment, tenant_id=x_tenant_id, project_id=x_project_id):
        return deployment_not_found(deployment_id, x_request_id)
    return deployment_to_read(deployment)


@router.get(
    "/deployments/{deployment_id}/instances",
    response_model=list[AgentInstanceRead],
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def list_deployment_instances(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> list[AgentInstanceRead] | JSONResponse:
    scope_error = require_scope(
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
    )
    if scope_error is not None:
        return scope_error
    assert x_tenant_id is not None
    auth = authenticate_api_key(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:read",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    try:
        deployment = service.deployments.get(deployment_id)
        if not deployment_in_scope(deployment, tenant_id=x_tenant_id, project_id=x_project_id):
            return deployment_not_found(deployment_id, x_request_id)
        return [instance_to_read(instance) for instance in service.list_instances(deployment_id)]
    except DeploymentNotFoundError:
        return deployment_not_found(deployment_id, x_request_id)


def control_response(
    deployment_id: str,
    *,
    action: Callable[[str, str], DeploymentRecord],
    service: DeploymentRuntimeControlService,
    request_id: str | None,
    tenant_id: str | None,
    project_id: str | None,
    authorization: str | None,
) -> DeploymentRead | JSONResponse:
    scope_error = require_scope(
        tenant_id=tenant_id,
        project_id=project_id,
        request_id=request_id,
    )
    if scope_error is not None:
        return scope_error
    assert tenant_id is not None
    auth = authenticate_api_key(
        authorization=authorization,
        tenant_id=tenant_id,
        project_id=project_id,
        required_scope="agent:deploy",
        request_id=request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    try:
        deployment_scope = service.deployments.get(deployment_id)
        if not deployment_in_scope(
            deployment_scope,
            tenant_id=tenant_id,
            project_id=project_id,
        ):
            return deployment_not_found(deployment_id, request_id)
        deployment = action(deployment_id, auth.actor_id)
    except DeploymentNotFoundError:
        return deployment_not_found(deployment_id, request_id)
    except PolicyDeniedError as exc:
        return error_response(
            status_code=403,
            error_code=exc.error_code,
            message=exc.reason,
            request_id=request_id,
            details={"deployment_id": deployment_id},
        )
    return deployment_to_read(deployment)


@router.post(
    "/deployments/{deployment_id}/activate",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def activate_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.activate(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


@router.post(
    "/deployments/{deployment_id}/pause",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def pause_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.pause(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


@router.post(
    "/deployments/{deployment_id}/resume",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def resume_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.resume(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


@router.post(
    "/deployments/{deployment_id}/drain",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def drain_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.drain(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


@router.post(
    "/deployments/{deployment_id}/stop",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def stop_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.stop(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


@router.post(
    "/deployments/{deployment_id}/restart",
    response_model=DeploymentRead,
    responses=CONTROL_RESPONSES,
)
def restart_deployment(
    deployment_id: str,
    service: DeploymentControlDep,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    x_actor_id: ActorIdHeader = None,
    authorization: AuthorizationHeader = None,
) -> DeploymentRead | JSONResponse:
    _ = x_actor_id
    return control_response(
        deployment_id,
        service=service,
        action=lambda value, actor_id: service.restart(
            value,
            actor_id=actor_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            request_id=x_request_id,
        ),
        request_id=x_request_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        authorization=authorization,
    )


def deployment_to_read(deployment: DeploymentRecord) -> DeploymentRead:
    return DeploymentRead.model_validate(deployment.__dict__)


def deployment_from_model(deployment: Deployment) -> DeploymentRecord:
    return DeploymentRecord(
        id=deployment.id,
        tenant_id=deployment.tenant_id,
        project_id=deployment.project_id,
        agent_id=deployment.agent_id,
        agent_version_id=deployment.agent_version_id,
        environment=deployment.environment,
        desired_status=DeploymentDesiredStatus(deployment.desired_status),
        runtime_status=DeploymentRuntimeStatus(deployment.runtime_status),
        replicas=deployment.replicas,
        config_json=deployment.config_json,
        last_runtime_error=deployment.last_runtime_error,
    )


def instance_to_read(instance: object) -> AgentInstanceRead:
    return AgentInstanceRead.model_validate(instance.__dict__)


def require_scope(
    *,
    tenant_id: str | None,
    project_id: str | None,
    request_id: str | None,
) -> JSONResponse | None:
    if tenant_id is not None and project_id is not None:
        return None
    return error_response(
        status_code=400,
        error_code="request_scope_required",
        message="X-Tenant-Id and X-Project-Id headers are required.",
        request_id=request_id,
        details={"required_headers": ["X-Tenant-Id", "X-Project-Id"]},
    )


def deployment_in_scope(
    deployment: DeploymentRecord,
    *,
    tenant_id: str | None,
    project_id: str | None,
) -> bool:
    return deployment.tenant_id == tenant_id and deployment.project_id == project_id


def deployment_not_found(deployment_id: str, request_id: str | None) -> JSONResponse:
    return error_response(
        status_code=404,
        error_code="deployment_not_found",
        message="Deployment was not found.",
        request_id=request_id,
        details={"deployment_id": deployment_id},
    )


def error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    request_id: str | None,
    details: dict[str, Any],
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error_code=error_code,
            message=message,
            request_id=request_id,
            details=details,
        ).model_dump(mode="json"),
    )
