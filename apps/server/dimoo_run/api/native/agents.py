from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dimoo_run.api.compat.auth import ProjectIdHeader, TenantIdHeader
from dimoo_run.api.dependencies import (
    AuthorizationHeader,
    IdempotencyKeyHeader,
    RequestIdHeader,
    authenticate_api_key,
    error_response,
)
from dimoo_run.api.native.dependencies import get_native_runtime
from dimoo_run.api.native.runtime import (
    NativeAgent,
    NativeAgentVersion,
    NativeRuntimeStore,
    SQLAlchemyNativeRuntimeStore,
)
from dimoo_run.runtime.idempotency import IdempotencyConflictError

router = APIRouter(tags=["native-agents"])
NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]


class AgentCreate(BaseModel):
    name: str
    description: str | None = None


class AgentRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    name: str
    description: str | None = None
    status: str


class AgentVersionCreate(BaseModel):
    version: str
    package_uri: str = "file://."
    framework: str = "langgraph"
    adapter: str = "langgraph"
    entrypoint: str = "agent:create_agent"
    capabilities: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)


class AgentVersionRead(BaseModel):
    id: str
    agent_id: str
    version: str
    package_uri: str
    framework: str
    adapter: str
    entrypoint: str
    capabilities: dict[str, Any]
    manifest: dict[str, Any]
    status: str


class AgentTaskCreate(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    version: str | None = None
    thread_id: str | None = None


class AgentTaskCreateResponse(BaseModel):
    run_id: str
    task_id: str
    status: str
    replayed: bool = False


def _auth(
    *,
    authorization: str | None,
    tenant_id: str | None,
    project_id: str | None,
    required_scope: str,
    request_id: str | None,
) -> tuple[str, str] | JSONResponse:
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


def _agent_to_read(agent: NativeAgent) -> AgentRead:
    return AgentRead.model_validate(agent.__dict__)


def _version_to_read(version: NativeAgentVersion) -> AgentVersionRead:
    return AgentVersionRead.model_validate(version.__dict__)


@router.post("/agents", status_code=201, response_model=AgentRead)
def create_agent(
    payload: AgentCreate,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> AgentRead | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:write",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id = auth
    agent = runtime.create_agent(
        tenant_id=tenant_id,
        project_id=project_id,
        name=payload.name,
        description=payload.description,
    )
    return _agent_to_read(agent)


@router.get("/agents", response_model=list[AgentRead])
def list_agents(
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[AgentRead] | JSONResponse:
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
        _agent_to_read(agent)
        for agent in runtime.list_agents(
            tenant_id=tenant_id,
            project_id=project_id,
        )
    ]


@router.get("/agents/{agent_id}", response_model=AgentRead)
def get_agent(
    agent_id: str,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> AgentRead | JSONResponse:
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
    agent = runtime.get_agent(agent_id, tenant_id=tenant_id, project_id=project_id)
    if agent is None:
        return error_response(
            status_code=404,
            error_code="agent_not_found",
            message="Agent was not found.",
            request_id=x_request_id,
            details={"agent_id": agent_id},
        )
    return _agent_to_read(agent)


@router.patch("/agents/{agent_id}", response_model=AgentRead)
def update_agent(
    agent_id: str,
    payload: AgentCreate,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> AgentRead | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:write",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id = auth
    existing = runtime.get_agent(agent_id, tenant_id=tenant_id, project_id=project_id)
    if existing is None:
        return error_response(
            status_code=404,
            error_code="agent_not_found",
            message="Agent was not found.",
            request_id=x_request_id,
            details={"agent_id": agent_id},
        )
    agent = runtime.update_agent(existing, name=payload.name, description=payload.description)
    return _agent_to_read(agent)


@router.delete("/agents/{agent_id}", response_model=AgentRead)
def delete_agent(
    agent_id: str,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> AgentRead | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:write",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id = auth
    existing = runtime.get_agent(agent_id, tenant_id=tenant_id, project_id=project_id)
    if existing is None:
        return error_response(
            status_code=404,
            error_code="agent_not_found",
            message="Agent was not found.",
            request_id=x_request_id,
            details={"agent_id": agent_id},
        )
    agent = runtime.archive_agent(existing)
    return _agent_to_read(agent)


@router.post("/agents/{agent_id}/versions", status_code=201, response_model=AgentVersionRead)
def create_agent_version(
    agent_id: str,
    payload: AgentVersionCreate,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> AgentVersionRead | JSONResponse:
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:write",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id = auth
    agent = runtime.get_agent(agent_id, tenant_id=tenant_id, project_id=project_id)
    if agent is None:
        return error_response(
            status_code=404,
            error_code="agent_not_found",
            message="Agent was not found.",
            request_id=x_request_id,
            details={"agent_id": agent_id},
        )
    version = runtime.create_version(agent=agent, **payload.model_dump())
    return _version_to_read(version)


@router.get("/agents/{agent_id}/versions", response_model=list[AgentVersionRead])
def list_agent_versions(
    agent_id: str,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> list[AgentVersionRead] | JSONResponse:
    agent = get_agent(agent_id, runtime, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(agent, JSONResponse):
        return agent
    return [
        _version_to_read(version)
        for version in runtime.list_versions(agent_id)
    ]


@router.get("/agents/{agent_id}/versions/{version}", response_model=AgentVersionRead)
def get_agent_version(
    agent_id: str,
    version: str,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> AgentVersionRead | JSONResponse:
    agent = get_agent(agent_id, runtime, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(agent, JSONResponse):
        return agent
    agent_version = runtime.get_version(agent_id, version)
    if agent_version is None:
        return error_response(
            status_code=404,
            error_code="agent_version_not_found",
            message="Agent version was not found.",
            request_id=x_request_id,
            details={"agent_id": agent_id, "version": version},
        )
    return _version_to_read(agent_version)


@router.post("/agents/{agent_id}/invoke", status_code=202, response_model=AgentTaskCreateResponse)
def invoke_agent(
    agent_id: str,
    payload: AgentTaskCreate,
    response: Response,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    idempotency_key: IdempotencyKeyHeader = None,
) -> AgentTaskCreateResponse | JSONResponse:
    return create_agent_task(
        agent_id,
        payload,
        response,
        runtime,
        authorization,
        x_tenant_id,
        x_project_id,
        x_request_id,
        idempotency_key,
    )


@router.post("/agents/{agent_id}/tasks", status_code=202, response_model=AgentTaskCreateResponse)
def create_agent_task(
    agent_id: str,
    payload: AgentTaskCreate,
    response: Response,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    idempotency_key: IdempotencyKeyHeader = None,
) -> AgentTaskCreateResponse | JSONResponse:
    _ = response
    auth = _auth(
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        required_scope="agent:invoke",
        request_id=x_request_id,
    )
    if isinstance(auth, JSONResponse):
        return auth
    tenant_id, project_id = auth
    agent = runtime.get_agent(agent_id, tenant_id=tenant_id, project_id=project_id)
    if agent is None:
        return error_response(
            status_code=404,
            error_code="agent_not_found",
            message="Agent was not found.",
            request_id=x_request_id,
            details={"agent_id": agent_id},
        )
    version = (
        runtime.get_version(agent_id, payload.version)
        if payload.version
        else runtime.latest_version(agent_id)
    )
    if version is None:
        return error_response(
            status_code=404,
            error_code="agent_version_not_found",
            message="Agent has no runnable version.",
            request_id=x_request_id,
            details={"agent_id": agent_id, "version": payload.version},
        )
    try:
        run, task, replayed = runtime.create_task_run(
            tenant_id=tenant_id,
            project_id=project_id,
            agent=agent,
            agent_version=version,
            input_data=payload.input,
            thread_id=payload.thread_id,
            idempotency_key=idempotency_key,
            endpoint=f"/v1/agents/{agent_id}/tasks",
            request_body=payload.model_dump(mode="json"),
        )
    except IdempotencyConflictError:
        return error_response(
            status_code=409,
            error_code="idempotency_key_conflict",
            message="Idempotency key was reused with a different request.",
            request_id=x_request_id,
            details={"idempotency_key": idempotency_key},
        )
    return AgentTaskCreateResponse(
        run_id=run.id,
        task_id=task.id,
        status=task.status.value,
        replayed=replayed,
    )


@router.post("/agents/{agent_id}/stream", status_code=202, response_model=AgentTaskCreateResponse)
def stream_agent(
    agent_id: str,
    payload: AgentTaskCreate,
    response: Response,
    runtime: NativeRuntimeDep,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
    idempotency_key: IdempotencyKeyHeader = None,
) -> AgentTaskCreateResponse | JSONResponse:
    return create_agent_task(
        agent_id,
        payload,
        response,
        runtime,
        authorization,
        x_tenant_id,
        x_project_id,
        x_request_id,
        idempotency_key,
    )
