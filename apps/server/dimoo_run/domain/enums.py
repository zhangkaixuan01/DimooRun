from enum import StrEnum


class DeploymentDesiredStatus(StrEnum):
    draft = "draft"
    active = "active"
    paused = "paused"
    draining = "draining"
    stopped = "stopped"
    archived = "archived"


class DeploymentRuntimeStatus(StrEnum):
    not_loaded = "not_loaded"
    warming_up = "warming_up"
    ready = "ready"
    degraded = "degraded"
    failed = "failed"
    draining = "draining"
    stopped = "stopped"


class AgentInstanceStatus(StrEnum):
    loading = "loading"
    ready = "ready"
    busy = "busy"
    idle = "idle"
    draining = "draining"
    evicted = "evicted"
    failed = "failed"


class RunStatus(StrEnum):
    pending = "pending"
    running = "running"
    interrupted = "interrupted"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    timeout = "timeout"


class RunAttemptStatus(StrEnum):
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    timeout = "timeout"
    cancelled = "cancelled"
    worker_lost = "worker_lost"


class TaskStatus(StrEnum):
    queued = "queued"
    leased = "leased"
    running = "running"
    retrying = "retrying"
    succeeded = "succeeded"
    failed = "failed"
    dead_letter = "dead_letter"
    cancelled = "cancelled"


class AuditActorType(StrEnum):
    user = "user"
    service_account = "service_account"
    system = "system"
    agent = "agent"
