from datetime import datetime
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
SUPPORTED_AGENT_RUNTIMES = {
    "langgraph": "langgraph",
    "langchain-agent": "langchain-agent",
    "deepagents": "deepagents",
}


class AgentCreate(BaseModel):
    name: str
    description: str | None = None


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class AgentRead(BaseModel):
    id: int
    tenant_id: int
    project_id: int
    name: str
    description: str | None = None
    status: str
    created_at: datetime | None = None


class AgentVersionCreate(BaseModel):
    version: str
    package_uri: str
    framework: str
    adapter: str
    entrypoint: str
    capabilities: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)


class AgentVersionUpdate(BaseModel):
    version: str | None = None
    package_uri: str | None = None
    framework: str | None = None
    adapter: str | None = None
    entrypoint: str | None = None
    capabilities: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    status: str | None = None


class AgentVersionRead(BaseModel):
    id: int
    agent_id: int
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
    run_id: int
    task_id: int
    status: str
    replayed: bool = False


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


def _agent_to_read(agent: NativeAgent) -> AgentRead:
    return AgentRead.model_validate(agent.__dict__)


def _version_to_read(version: NativeAgentVersion) -> AgentVersionRead:
    return AgentVersionRead.model_validate(version.__dict__)


def _validate_agent_runtime(
    *,
    framework: str,
    adapter: str,
    request_id: str | None,
) -> JSONResponse | None:
    expected_framework = SUPPORTED_AGENT_RUNTIMES.get(adapter)
    if expected_framework == framework:
        return None
    return error_response(
        status_code=400,
        error_code="unsupported_agent_runtime",
        message="AgentVersion framework and adapter must use a supported runtime pair.",
        request_id=request_id,
        details={
            "framework": framework,
            "adapter": adapter,
            "supported": [
                {"framework": framework_name, "adapter": adapter_name}
                for adapter_name, framework_name in SUPPORTED_AGENT_RUNTIMES.items()
            ],
        },
    )


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
    agent_id: int,
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
    agent_id: int,
    payload: AgentUpdate,
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
    fields_set = payload.model_fields_set
    agent = runtime.update_agent(
        existing,
        name=payload.name if "name" in fields_set and payload.name is not None else existing.name,
        description=payload.description if "description" in fields_set else existing.description,
        status=(
            payload.status
            if "status" in fields_set and payload.status is not None
            else existing.status
        ),
    )
    return _agent_to_read(agent)


@router.delete("/agents/{agent_id}", response_model=AgentRead)
def delete_agent(
    agent_id: int,
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
    agent_id: int,
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
    runtime_error = _validate_agent_runtime(
        framework=payload.framework,
        adapter=payload.adapter,
        request_id=x_request_id,
    )
    if runtime_error is not None:
        return runtime_error
    version = runtime.create_version(agent=agent, **payload.model_dump())
    return _version_to_read(version)


@router.get("/agents/{agent_id}/versions", response_model=list[AgentVersionRead])
def list_agent_versions(
    agent_id: int,
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
    agent_id: int,
    version: str,
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


@router.patch("/agents/{agent_id}/versions/{version}", response_model=AgentVersionRead)
def update_agent_version(
    agent_id: int,
    version: str,
    payload: AgentVersionUpdate,
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
    existing = runtime.get_version(agent_id, version)
    if existing is None:
        return error_response(
            status_code=404,
            error_code="agent_version_not_found",
            message="Agent version was not found.",
            request_id=x_request_id,
            details={"agent_id": agent_id, "version": version},
        )
    next_version = payload.version or existing.version
    if next_version != existing.version and runtime.get_version(agent_id, next_version) is not None:
        return error_response(
            status_code=409,
            error_code="agent_version_conflict",
            message="Agent version already exists.",
            request_id=x_request_id,
            details={"agent_id": agent_id, "version": next_version},
        )
    next_framework = payload.framework or existing.framework
    next_adapter = payload.adapter or existing.adapter
    runtime_error = _validate_agent_runtime(
        framework=next_framework,
        adapter=next_adapter,
        request_id=x_request_id,
    )
    if runtime_error is not None:
        return runtime_error
    updated = runtime.update_version(
        existing,
        version=next_version,
        package_uri=payload.package_uri or existing.package_uri,
        framework=next_framework,
        adapter=next_adapter,
        entrypoint=payload.entrypoint or existing.entrypoint,
        capabilities=(
            payload.capabilities if payload.capabilities is not None else existing.capabilities
        ),
        manifest=payload.manifest if payload.manifest is not None else existing.manifest,
        status=payload.status or existing.status,
    )
    return _version_to_read(updated)


@router.delete("/agents/{agent_id}/versions/{version}", response_model=AgentVersionRead)
def delete_agent_version(
    agent_id: int,
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
    existing = runtime.get_version(agent_id, version)
    if existing is None:
        return error_response(
            status_code=404,
            error_code="agent_version_not_found",
            message="Agent version was not found.",
            request_id=x_request_id,
            details={"agent_id": agent_id, "version": version},
        )
    archived = runtime.archive_version(existing)
    return _version_to_read(archived)


@router.post("/agents/{agent_id}/invoke", status_code=202, response_model=AgentTaskCreateResponse)
def invoke_agent(
    agent_id: int,
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
    agent_id: int,
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
    if agent.status != "active":
        return error_response(
            status_code=409,
            error_code="agent_not_active",
            message="Agent must be active before it can accept new tasks.",
            request_id=x_request_id,
            details={"agent_id": agent_id, "status": agent.status},
        )
    if version.status != "ready":
        return error_response(
            status_code=409,
            error_code="agent_version_not_ready",
            message="Agent version must be ready before it can accept new tasks.",
            request_id=x_request_id,
            details={
                "agent_id": agent_id,
                "version": version.version,
                "status": version.status,
            },
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
    agent_id: int,
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
