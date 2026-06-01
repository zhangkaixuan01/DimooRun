from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RuntimeContext:
    tenant_id: int
    project_id: int | None
    run_id: int
    task_id: int | None
    agent_id: int
    agent_version_id: int
    deployment_id: int | None
    user_id: int | None = None
    service_account_id: int | None = None
    thread_id: str | None = None
    session_id: int | None = None
    request_id: str | None = None
    attempt_id: int | None = None
    trace_id: str | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None
    environment: str | None = None
    framework: str | None = None
    adapter: str | None = None
    agent_version: str | None = None
    deadline_at: datetime | None = None
    permissions: list[str] = field(default_factory=list)
    secrets: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self, *, include_none: bool = False) -> dict[str, Any]:
        metadata = {
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "agent_version_id": self.agent_version_id,
            "deployment_id": self.deployment_id,
            "user_id": self.user_id,
            "service_account_id": self.service_account_id,
            "thread_id": self.thread_id,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "attempt_id": self.attempt_id,
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "environment": self.environment,
            "framework": self.framework,
            "adapter": self.adapter,
            "agent_version": self.agent_version,
            "metadata": self.metadata,
        }
        if include_none:
            return metadata
        return {key: value for key, value in metadata.items() if value is not None}
