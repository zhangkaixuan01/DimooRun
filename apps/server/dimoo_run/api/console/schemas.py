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
    environment: str
    status: str
    drain_status: str
    version: str
    queues: list[str] = Field(default_factory=list)
    capacity: int
    active_attempts: int
    active_runs: int
    heartbeat_age_seconds: float | None = None
    last_error: str | None = None
    liveness: str
    readiness: str
    retrying_tasks: int = 0
    dead_letter_tasks: int = 0
    deployment_ids: list[int] = Field(default_factory=list)
    restart_requested_at: str | None = None


class ConsoleControlAction(BaseModel):
    action: str
    label: str
    available: bool
    disabled_reasons: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    audit_required: bool = False


class ConsoleWorkerDetail(ConsoleWorkerHealth):
    active_task_ids: list[int] = Field(default_factory=list)
    active_run_ids: list[int] = Field(default_factory=list)
    actions: list[ConsoleControlAction] = Field(default_factory=list)


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


class ConsoleRuntimeTrendPoint(BaseModel):
    label: str
    runs: int
    success_rate: float


class ConsoleRuntimeOverview(BaseModel):
    summary: ConsoleDashboardSummary
    deployment_health: list[ConsoleDeploymentHealth]
    worker_health: list[ConsoleWorkerHealth]
    recent_failures: list[ConsoleRecentFailure]
    pending_actions: list[ConsolePendingAction]
    trend_points: list[ConsoleRuntimeTrendPoint] = Field(default_factory=list)


class ConsoleAgentInstance(BaseModel):
    id: int
    deployment_id: int
    environment: str
    agent_id: int
    agent_version_id: int
    worker_id: str
    status: str
    active_runs: int
    recent_failures: int
    concurrency_limit: int
    runtime_config_hash: str
    execution_profile_id: str | None = None
    cache_key: str
    loaded_at: str | None = None
    heartbeat_at: str | None = None
    last_error: str | None = None


class ConsoleAgentInstanceDetail(ConsoleAgentInstance):
    deployment_desired_status: str
    deployment_runtime_status: str


class ConsoleQueuePressure(BaseModel):
    queue: str
    queue_backlog: int
    leased: int
    running: int
    retrying: int
    dead_letter: int
    oldest_task_age_seconds: float | None = None


class ConsoleCapacitySummary(BaseModel):
    queue_backlog: int
    active_attempts: int
    total_capacity: int
    saturation_ratio: float
    time_to_drain_seconds: int
    retry_pressure: int
    dead_letter_pressure: int
    recommended_action: str
    recommended_reason: str
    active_workers: int
    draining_workers: int
    quarantined_workers: int
    critical_attempts: int
    queues: list[ConsoleQueuePressure] = Field(default_factory=list)
