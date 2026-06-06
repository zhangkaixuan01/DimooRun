from pydantic import BaseModel, Field


class ConsoleDashboardSummary(BaseModel):
    run_count_today: int
    success_rate: float
    p95_latency_ms: int
    p99_latency_ms: int
    queue_backlog: int
    worker_ready: int
    worker_total: int
    monthly_cost_usd: float
    pending_approvals: int
    running_runs: int
    active_incidents: int


class ConsoleDeploymentHealth(BaseModel):
    deployment_id: int
    environment: str
    desired_status: str
    runtime_status: str
    replicas: int
    queue_backlog: int
    running_runs: int
    last_runtime_error: str | None = None


class ConsoleWorkerHealth(BaseModel):
    worker_id: str
    deployment_id: int
    environment: str
    status: str
    queue_backlog: int
    running_runs: int


class ConsoleRecentFailure(BaseModel):
    run_id: int
    deployment_id: int | None
    agent_id: int
    agent_version_id: int
    status: str
    error_summary: str
    created_at: str


class ConsoleActionAvailability(BaseModel):
    resource_type: str
    resource_id: int
    action: str
    available: bool
    disabled_reasons: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    policy_warnings: list[str] = Field(default_factory=list)
    audit_required: bool = False


class ConsoleActionSummary(BaseModel):
    actions: list[ConsoleActionAvailability]


class ConsolePendingAction(BaseModel):
    resource_type: str
    resource_id: int
    action: str
    label: str
    disabled_reason: str | None = None
    required_permissions: list[str] = Field(default_factory=list)
    audit_required: bool = False


class ConsoleRuntimeOverview(BaseModel):
    summary: ConsoleDashboardSummary
    deployment_health: list[ConsoleDeploymentHealth]
    worker_health: list[ConsoleWorkerHealth]
    recent_failures: list[ConsoleRecentFailure]
    pending_actions: list[ConsolePendingAction]
