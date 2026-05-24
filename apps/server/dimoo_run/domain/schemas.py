from typing import Any

from pydantic import BaseModel, Field

from dimoo_run.domain.enums import (
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
    id: str
    tenant_id: str
    project_id: str
    agent_id: str
    agent_version_id: str
    environment: str
    desired_status: DeploymentDesiredStatus
    runtime_status: DeploymentRuntimeStatus
    replicas: int
    last_runtime_error: str | None = None


class RunRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    user_id: str | None = None
    service_account_id: str | None = None
    agent_id: str
    agent_version_id: str
    deployment_id: str | None = None
    session_id: str | None = None
    framework: str | None = None
    adapter: str | None = None
    thread_id: str | None = None
    trace_id: str | None = None
    idempotency_key: str | None = None
    status: RunStatus
    input_ref: str | None = None
    output_ref: str | None = None
    error: str | None = None
