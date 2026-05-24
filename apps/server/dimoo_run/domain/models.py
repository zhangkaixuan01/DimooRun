from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from dimoo_run.domain.enums import (
    AgentInstanceStatus,
    AuditActorType,
    DeploymentDesiredStatus,
    DeploymentRuntimeStatus,
    RunAttemptStatus,
    RunStatus,
    TaskStatus,
)
from dimoo_run.persistence.database import (
    AuditMixin,
    Base,
    IdMixin,
    TenantProjectMixin,
    TimestampMixin,
)


class Tenant(IdMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_projects_tenant_slug"),)

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class ServiceAccount(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "service_accounts"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Role(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class Permission(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "permissions"

    resource: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class APIKey(IdMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),)

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_type: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotation_policy_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Agent(IdMixin, TimestampMixin, Base):
    __tablename__ = "agents"
    __table_args__ = (
        Index(
            "uq_agents_project_name_active",
            "project_id",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class AgentVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
    )

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    framework: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter: Mapped[str] = mapped_column(String(128), nullable=False)
    capabilities_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    entrypoint: Mapped[str] = mapped_column(String(512), nullable=False)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    adapter_api_version: Mapped[str | None] = mapped_column(String(64))
    framework_version: Mapped[str | None] = mapped_column(String(128))
    manifest_schema_version: Mapped[str | None] = mapped_column(String(64))
    capability_schema_version: Mapped[str | None] = mapped_column(String(64))
    event_schema_version: Mapped[str | None] = mapped_column(String(64))
    compatibility_status: Mapped[str | None] = mapped_column(String(64))
    compatibility_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(64), default="draft", nullable=False)


class Deployment(IdMixin, TimestampMixin, Base):
    __tablename__ = "deployments"
    __table_args__ = (
        Index(
            "uq_deployments_project_environment_agent_active",
            "project_id",
            "environment",
            "agent_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    agent_version_id: Mapped[str] = mapped_column(
        ForeignKey("agent_versions.id"), nullable=False, index=True
    )
    environment: Mapped[str] = mapped_column(String(128), nullable=False)
    desired_status: Mapped[str] = mapped_column(
        String(64), default=DeploymentDesiredStatus.draft.value, nullable=False
    )
    runtime_status: Mapped[str] = mapped_column(
        String(64), default=DeploymentRuntimeStatus.not_loaded.value, nullable=False
    )
    replicas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_runtime_error: Mapped[str | None] = mapped_column(Text)


class AgentInstance(IdMixin, TimestampMixin, Base):
    __tablename__ = "agent_instances"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    deployment_id: Mapped[str] = mapped_column(ForeignKey("deployments.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    agent_version_id: Mapped[str] = mapped_column(ForeignKey("agent_versions.id"), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    execution_profile_id: Mapped[str | None] = mapped_column(String(128))
    cache_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(
        String(64), default=AgentInstanceStatus.loading.value, nullable=False
    )
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    running_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class SessionModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "sessions"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    service_account_id: Mapped[str | None] = mapped_column(ForeignKey("service_accounts.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Run(IdMixin, AuditMixin, Base):
    __tablename__ = "runs"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    service_account_id: Mapped[str | None] = mapped_column(ForeignKey("service_accounts.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    agent_version_id: Mapped[str] = mapped_column(ForeignKey("agent_versions.id"), nullable=False)
    deployment_id: Mapped[str | None] = mapped_column(ForeignKey("deployments.id"))
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"))
    framework: Mapped[str | None] = mapped_column(String(128))
    adapter: Mapped[str | None] = mapped_column(String(128))
    thread_id: Mapped[str | None] = mapped_column(String(255))
    trace_id: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(64), default=RunStatus.pending.value, nullable=False)
    input_ref: Mapped[str | None] = mapped_column(String(1024))
    output_ref: Mapped[str | None] = mapped_column(String(1024))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunAttempt(IdMixin, AuditMixin, Base):
    __tablename__ = "run_attempts"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"))
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(
        String(64), default=RunAttemptStatus.running.value, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class Task(IdMixin, AuditMixin, Base):
    __tablename__ = "tasks"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default=TaskStatus.queued.value, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    queue: Mapped[str] = mapped_column(String(128), default="default", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    dead_letter_reason: Mapped[str | None] = mapped_column(Text)


class Event(IdMixin, AuditMixin, Base):
    __tablename__ = "events"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("run_attempts.id"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(128), nullable=False)
    framework: Mapped[str | None] = mapped_column(String(128))
    payload_ref: Mapped[str | None] = mapped_column(String(1024))
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    visibility_level: Mapped[str] = mapped_column(String(64), default="internal", nullable=False)


class CheckpointIndex(IdMixin, AuditMixin, Base):
    __tablename__ = "checkpoint_indexes"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    checkpoint_ns: Mapped[str | None] = mapped_column(String(255))
    checkpoint_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_uri: Mapped[str] = mapped_column(String(1024), nullable=False)


class Tool(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "tools"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(64), default="read", nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class Secret(IdMixin, TimestampMixin, Base):
    __tablename__ = "secrets"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(IdMixin, AuditMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"info": {"immutable": True}}

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    actor_id: Mapped[str | None] = mapped_column(String(64))
    actor_type: Mapped[str] = mapped_column(
        String(64), default=AuditActorType.system.value, nullable=False
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(128))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    request_id: Mapped[str | None] = mapped_column(String(255))
    trace_id: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class IdempotencyRecord(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "endpoint",
            "idempotency_key",
            name="uq_idempotency_records_scope_key",
        ),
    )

    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    response_ref: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def create_metadata_model(table_name: str) -> type[Base]:
    return type(
        "".join(part.capitalize() for part in table_name.split("_")),
        (IdMixin, TenantProjectMixin, TimestampMixin, Base),
        {
            "__tablename__": table_name,
            "__table_args__": {"info": {"placeholder": True}},
            "status": mapped_column(String(64), default="active", nullable=False),
            "metadata_json": mapped_column(JSON, default=dict, nullable=False),
        },
    )


for _table_name in [
    "published_surfaces",
    "ingress_routes",
    "catalog_items",
    "prompt_assets",
    "config_assets",
    "templates",
    "run_graph_nodes",
    "run_graph_edges",
    "datasets",
    "dataset_items",
    "experiments",
    "experiment_runs",
    "evaluation_results",
    "feedback",
    "scheduled_runs",
    "batch_runs",
    "replay_jobs",
    "memory_blocks",
    "semantic_store_providers",
    "model_gateways",
    "model_policies",
    "model_usage_snapshots",
    "policies",
    "policy_decisions",
    "human_tasks",
    "approval_requests",
    "approval_policies",
    "artifacts",
    "notification_channels",
    "alert_rules",
    "incident_events",
    "webhook_subscriptions",
    "extensions",
    "backup_plans",
    "restore_jobs",
]:
    globals()["".join(part.capitalize() for part in _table_name.split("_"))] = (
        create_metadata_model(_table_name)
    )
