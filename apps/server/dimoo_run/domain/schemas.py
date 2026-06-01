from typing import Any

from pydantic import BaseModel, Field

from dimoo_run.domain.enums import (
    AgentInstanceStatus,
    DeploymentDesiredStatus,
    DeploymentRuntimeStatus,
    RunStatus,
)


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class DeploymentRead(BaseModel):
    id: int
    tenant_id: int
    project_id: int
    agent_id: int
    agent_version_id: int
    environment: str
    desired_status: DeploymentDesiredStatus
    runtime_status: DeploymentRuntimeStatus
    replicas: int
    last_runtime_error: str | None = None


class AgentInstanceRead(BaseModel):
    id: int
    tenant_id: int
    project_id: int
    deployment_id: int
    agent_id: int
    agent_version_id: int
    worker_id: str
    execution_profile_id: str | None = None
    cache_key: str
    status: AgentInstanceStatus
    running_runs: int
    error: str | None = None


class RunRead(BaseModel):
    id: int
    tenant_id: int
    project_id: int
    user_id: int | None = None
    service_account_id: int | None = None
    agent_id: int
    agent_version_id: int
    deployment_id: int | None = None
    session_id: int | None = None
    framework: str | None = None
    adapter: str | None = None
    thread_id: str | None = None
    trace_id: str | None = None
    idempotency_key: str | None = None
    status: RunStatus
    input_ref: str | None = None
    output_ref: str | None = None
    error: str | None = None
