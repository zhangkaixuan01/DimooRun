from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
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

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class Environment(IdMixin, TimestampMixin, Base):
    __tablename__ = "environments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "environment",
            name="uq_environments_project_environment",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class PlatformControlSetting(IdMixin, TimestampMixin, Base):
    __tablename__ = "platform_control_settings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "environment",
            "scope_kind",
            "setting_key",
            name="uq_platform_control_setting_scope_key",
        ),
        Index(
            "ix_platform_control_settings_environment",
            "environment",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )
    environment: Mapped[str | None] = mapped_column(String(128))
    scope_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(128), nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class ServiceAccount(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "service_accounts"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    permissions_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
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


class ConsoleOperator(IdMixin, TimestampMixin, Base):
    __tablename__ = "console_operators"
    __table_args__ = (UniqueConstraint("email", name="uq_console_operators_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsoleOperatorCredential(IdMixin, TimestampMixin, Base):
    __tablename__ = "console_operator_credentials"
    __table_args__ = (
        UniqueConstraint("operator_id", name="uq_console_operator_credentials_operator"),
    )

    operator_id: Mapped[int] = mapped_column(
        ForeignKey("console_operators.id"), nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsoleOperatorSession(IdMixin, TimestampMixin, Base):
    __tablename__ = "console_operator_sessions"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_console_sessions_token_hash"),)

    operator_id: Mapped[int] = mapped_column(
        ForeignKey("console_operators.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(128))
    ip_address: Mapped[str | None] = mapped_column(String(128))
    user_agent: Mapped[str | None] = mapped_column(String(512))


class ConsoleOperatorAllowedScope(IdMixin, TimestampMixin, Base):
    __tablename__ = "console_operator_allowed_scopes"
    __table_args__ = (
        UniqueConstraint(
            "operator_id",
            "tenant_id",
            "project_id",
            "environment",
            name="uq_console_operator_scope",
        ),
    )

    operator_id: Mapped[int] = mapped_column(
        ForeignKey("console_operators.id"), nullable=False, index=True
    )
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    environment: Mapped[str] = mapped_column(String(128), nullable=False)


class ConsoleRole(IdMixin, TimestampMixin, Base):
    __tablename__ = "console_roles"
    __table_args__ = (UniqueConstraint("name", name="uq_console_roles_name"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class ConsolePermission(IdMixin, TimestampMixin, Base):
    __tablename__ = "console_permissions"
    __table_args__ = (UniqueConstraint("code", name="uq_console_permissions_code"),)

    code: Mapped[str] = mapped_column(String(255), nullable=False)
    resource: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class ConsoleOperatorRole(IdMixin, TimestampMixin, Base):
    __tablename__ = "console_operator_roles"
    __table_args__ = (UniqueConstraint("operator_id", "role_id", name="uq_console_operator_role"),)

    operator_id: Mapped[int] = mapped_column(
        ForeignKey("console_operators.id"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(ForeignKey("console_roles.id"), nullable=False, index=True)


class ConsoleRolePermission(IdMixin, TimestampMixin, Base):
    __tablename__ = "console_role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_console_role_permission"),
    )

    role_id: Mapped[int] = mapped_column(ForeignKey("console_roles.id"), nullable=False, index=True)
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("console_permissions.id"), nullable=False, index=True
    )


class ConsoleOperatorPermission(IdMixin, TimestampMixin, Base):
    __tablename__ = "console_operator_permissions"
    __table_args__ = (
        UniqueConstraint("operator_id", "permission_id", name="uq_console_operator_permission"),
    )

    operator_id: Mapped[int] = mapped_column(
        ForeignKey("console_operators.id"), nullable=False, index=True
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("console_permissions.id"), nullable=False, index=True
    )


class APIKey(IdMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),)

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_type: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("service_accounts.id"), nullable=False, index=True
    )
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
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

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class AgentVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
    )

    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
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

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    agent_version_id: Mapped[int] = mapped_column(
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

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id"), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    agent_version_id: Mapped[int] = mapped_column(ForeignKey("agent_versions.id"), nullable=False)
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


class WorkerSnapshot(IdMixin, TimestampMixin, Base):
    __tablename__ = "worker_snapshots"
    __table_args__ = (
        Index(
            "uq_worker_snapshots_scope_worker_active",
            "tenant_id",
            "project_id",
            "environment",
            "worker_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        index=True,
    )
    environment: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), default="idle", nullable=False)
    drain_status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    version: Mapped[str] = mapped_column(String(128), default="unknown", nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    restart_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class SessionModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "sessions"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    service_account_id: Mapped[int | None] = mapped_column(ForeignKey("service_accounts.id"))
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Run(IdMixin, AuditMixin, Base):
    __tablename__ = "runs"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    service_account_id: Mapped[int | None] = mapped_column(ForeignKey("service_accounts.id"))
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    agent_version_id: Mapped[int] = mapped_column(ForeignKey("agent_versions.id"), nullable=False)
    deployment_id: Mapped[int | None] = mapped_column(ForeignKey("deployments.id"))
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
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

    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
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

    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
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
    fencing_token: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    dead_letter_reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Event(IdMixin, AuditMixin, Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_events_run_sequence"),)

    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("run_attempts.id"))
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(128), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_id: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    framework: Mapped[str | None] = mapped_column(String(128))
    payload_ref: Mapped[str | None] = mapped_column(String(1024))
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    visibility_level: Mapped[str] = mapped_column(String(64), default="internal", nullable=False)


class CheckpointIndex(IdMixin, AuditMixin, Base):
    __tablename__ = "checkpoint_indexes"

    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    checkpoint_ns: Mapped[str | None] = mapped_column(String(255))
    checkpoint_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_uri: Mapped[str] = mapped_column(String(1024), nullable=False)


class PublishedSurface(IdMixin, AuditMixin, Base):
    __tablename__ = "published_surfaces"
    __table_args__ = (
        Index(
            "uq_published_surfaces_deployment_type_active",
            "deployment_id",
            "type",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class PublishedSurfaceEvidenceBundle(IdMixin, AuditMixin, Base):
    __tablename__ = "published_surface_evidence_bundles"
    __table_args__ = (
        Index(
            "uq_published_surface_evidence_bundle_active",
            "surface_id",
            "bundle_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    surface_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    bundle_id: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="recorded", nullable=False)
    export_status: Mapped[str] = mapped_column(String(64), default="not_exported", nullable=False)
    evidence_bundle_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    redacted_payload_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    last_exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_export_request_id: Mapped[str | None] = mapped_column(String(255))
    retention_policy_id: Mapped[str | None] = mapped_column(String(128))
    retain_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archive_reason: Mapped[str | None] = mapped_column(String(1024))
    archive_request_id: Mapped[str | None] = mapped_column(String(255))


class PublishedSurfaceRequestLog(IdMixin, AuditMixin, Base):
    __tablename__ = "published_surface_request_logs"
    __table_args__ = (
        Index(
            "uq_published_surface_request_log_active",
            "surface_id",
            "request_log_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    surface_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    request_log_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(255), index=True)
    request_id: Mapped[str | None] = mapped_column(String(255), index=True)
    ingress_source: Mapped[str | None] = mapped_column(String(64))
    request_log_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence_bundle_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )


class PublishedSurfaceRollout(IdMixin, AuditMixin, Base):
    __tablename__ = "published_surface_rollouts"
    __table_args__ = (
        Index(
            "uq_published_surface_rollout_active",
            "surface_id",
            "rollout_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    surface_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    rollout_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String(255), index=True)
    rollout_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence_bundle_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )


class PublishedSurfaceBinding(IdMixin, AuditMixin, Base):
    __tablename__ = "published_surface_bindings"
    __table_args__ = (
        Index(
            "uq_published_surface_binding_active",
            "surface_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
        Index(
            "uq_published_surface_route_active",
            "route_path",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    surface_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    deployment_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_path: Mapped[str] = mapped_column(String(512), nullable=False)
    auth_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[str | None] = mapped_column(String(64))
    surface_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class IngressRoute(IdMixin, AuditMixin, Base):
    __tablename__ = "ingress_routes"
    __table_args__ = (
        Index(
            "uq_ingress_routes_surface_path_active",
            "surface_id",
            "path",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    surface_id: Mapped[int] = mapped_column(ForeignKey("published_surfaces.id"), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    custom_domain: Mapped[str | None] = mapped_column(String(255))
    auth_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    cors_policy_id: Mapped[str | None] = mapped_column(String(64))
    rate_limit_policy_id: Mapped[str | None] = mapped_column(String(64))
    request_transform_ref: Mapped[str | None] = mapped_column(String(1024))
    response_transform_ref: Mapped[str | None] = mapped_column(String(1024))
    access_log_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Tool(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "tools"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(64), default="read", nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class Secret(IdMixin, TimestampMixin, Base):
    __tablename__ = "secrets"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExecutionProfile(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "execution_profiles"
    __table_args__ = (
        Index(
            "uq_execution_profiles_scope_name_active",
            "tenant_id",
            "project_id",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    isolation_level: Mapped[str] = mapped_column(String(64), nullable=False)
    image: Mapped[str | None] = mapped_column(String(512))
    python_version: Mapped[str | None] = mapped_column(String(64))
    dependency_lock_required: Mapped[bool] = mapped_column(default=True, nullable=False)
    network_policy: Mapped[str] = mapped_column(String(128), nullable=False)
    filesystem_policy: Mapped[str] = mapped_column(String(128), nullable=False)
    cpu_limit: Mapped[str | None] = mapped_column(String(64))
    memory_limit: Mapped[str | None] = mapped_column(String(64))
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    allowed_env_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_secret_refs_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_gateway_refs_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class Policy(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "policies"

    type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    risk_level: Mapped[str | None] = mapped_column(String(64))
    condition_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class PolicyDecisionRecord(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "policy_decisions"

    policy_id: Mapped[int | None] = mapped_column(ForeignKey("policies.id"))
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    actor_id: Mapped[str | None] = mapped_column(String(64))
    actor_type: Mapped[str | None] = mapped_column(String(64))
    matched_policy_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ModelGateway(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "model_gateways"
    __table_args__ = (
        Index(
            "uq_model_gateways_scope_name_active",
            "tenant_id",
            "project_id",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    credential_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    default_model_group: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ModelPolicy(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "model_policies"

    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"))
    agent_version_id: Mapped[int | None] = mapped_column(ForeignKey("agent_versions.id"))
    gateway_id: Mapped[int] = mapped_column(ForeignKey("model_gateways.id"), nullable=False)
    allowed_models_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    denied_models_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    default_model: Mapped[str] = mapped_column(String(255), nullable=False)
    max_tokens_per_run: Mapped[int | None] = mapped_column(Integer)
    max_cost_per_run: Mapped[float | None] = mapped_column(Float)
    max_cost_per_day: Mapped[float | None] = mapped_column(Float)
    fallback_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    on_budget_exceeded: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class ModelUsageSnapshot(IdMixin, TimestampMixin, Base):
    __tablename__ = "model_usage_snapshots"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("run_attempts.id"))
    gateway_id: Mapped[int] = mapped_column(ForeignKey("model_gateways.id"), nullable=False)
    gateway_request_id: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(128))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(16), default="USD", nullable=False)
    raw_usage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class HumanTask(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "human_tasks"

    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"))
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("run_attempts.id"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    assignee_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assignee_role: Mapped[str | None] = mapped_column(String(128))
    payload_ref: Mapped[str | None] = mapped_column(String(1024))
    decision_ref: Mapped[str | None] = mapped_column(String(1024))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApprovalRequest(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "approval_requests"

    human_task_id: Mapped[int] = mapped_column(ForeignKey("human_tasks.id"), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    decision_ref: Mapped[str | None] = mapped_column(String(1024))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ApprovalPolicy(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "approval_policies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_level: Mapped[str | None] = mapped_column(String(64))
    condition_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    required_role: Mapped[str] = mapped_column(String(128), nullable=False)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    on_timeout: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class CatalogItem(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "catalog_items"
    __table_args__ = (
        Index(
            "uq_catalog_items_scope_type_name_version_active",
            "tenant_id",
            "project_id",
            "type",
            "name",
            "version",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    type: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    capabilities_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(64), nullable=False)
    required_secrets_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    required_permissions_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    runtime_requirements_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class PromptAsset(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "prompt_assets"
    __table_args__ = (
        Index(
            "uq_prompt_assets_scope_name_version_active",
            "tenant_id",
            "project_id",
            "name",
            "version",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    content_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    variables_schema_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    visibility_level: Mapped[str] = mapped_column(String(64), default="internal", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ConfigAsset(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "config_assets"
    __table_args__ = (
        Index(
            "uq_config_assets_scope_name_version_active",
            "tenant_id",
            "project_id",
            "name",
            "version",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    content_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    environment: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Template(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "templates"
    __table_args__ = (
        Index(
            "uq_templates_scope_type_name_version_active",
            "tenant_id",
            "project_id",
            "type",
            "name",
            "version",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    type: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    content_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Artifact(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "artifacts"

    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"))
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("run_attempts.id"))
    event_id: Mapped[str | None] = mapped_column(String(512))
    artifact_type: Mapped[str] = mapped_column(String(128), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum: Mapped[str] = mapped_column(String(255), nullable=False)
    visibility_level: Mapped[str] = mapped_column(String(64), default="internal", nullable=False)
    retention_policy_id: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RunGraphNode(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "run_graph_nodes"
    __table_args__ = (
        UniqueConstraint("run_id", "node_key", name="uq_run_graph_nodes_run_node_key"),
    )

    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("run_attempts.id"))
    node_key: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    framework_node_id: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_ref: Mapped[str | None] = mapped_column(String(1024))
    output_ref: Mapped[str | None] = mapped_column(String(1024))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RunGraphEdge(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "run_graph_edges"

    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    source_node_id: Mapped[int] = mapped_column(ForeignKey("run_graph_nodes.id"), nullable=False)
    target_node_id: Mapped[int] = mapped_column(ForeignKey("run_graph_nodes.id"), nullable=False)
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Dataset(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (
        Index(
            "uq_datasets_scope_name_active",
            "tenant_id",
            "project_id",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    visibility_level: Mapped[str] = mapped_column(String(64), default="internal", nullable=False)


class DatasetItem(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "dataset_items"

    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    source_run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"))
    input_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    output_ref: Mapped[str | None] = mapped_column(String(1024))
    expected_ref: Mapped[str | None] = mapped_column(String(1024))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Experiment(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "experiments"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    baseline_agent_version_id: Mapped[int | None] = mapped_column(ForeignKey("agent_versions.id"))
    candidate_agent_version_id: Mapped[int] = mapped_column(
        ForeignKey("agent_versions.id"), nullable=False
    )
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    evaluator_config_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    status: Mapped[str] = mapped_column(String(64), default="draft", nullable=False)


class ExperimentRun(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "experiment_runs"

    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="running", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class EvaluationResult(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_results"

    experiment_run_id: Mapped[int] = mapped_column(ForeignKey("experiment_runs.id"), nullable=False)
    evaluator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Feedback(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    rating: Mapped[str | None] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class MemoryBlock(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "memory_blocks"

    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"))
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class SemanticStoreProvider(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "semantic_store_providers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_gateway_id: Mapped[int | None] = mapped_column(ForeignKey("model_gateways.id"))
    connection_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    retention_policy_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ObservabilityExporter(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "observability_exporters"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exporter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class SandboxPolicy(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "sandbox_policies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    isolation_level: Mapped[str] = mapped_column(String(64), default="process", nullable=False)
    network_policy: Mapped[str] = mapped_column(String(128), default="deny_all", nullable=False)
    filesystem_policy: Mapped[str] = mapped_column(String(128), default="read_only", nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ContainerPoolPolicy(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "container_pool_policies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    max_containers: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    cpu_limit: Mapped[str] = mapped_column(String(64), default="1000m", nullable=False)
    memory_limit: Mapped[str] = mapped_column(String(64), default="1Gi", nullable=False)
    idle_timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class NotificationChannel(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "notification_channels"

    type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CostSavedView(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "cost_saved_views"
    __table_args__ = (
        Index(
            "uq_cost_saved_views_scope_name_active",
            "tenant_id",
            "project_id",
            "environment",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str | None] = mapped_column(String(128))
    group_by: Mapped[str] = mapped_column(String(64), nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CostBudgetPolicy(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "cost_budget_policies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str | None] = mapped_column(String(128))
    scope_type: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_ref: Mapped[str | None] = mapped_column(String(255))
    threshold_usd: Mapped[float] = mapped_column(Float, nullable=False)
    reset_window: Mapped[str] = mapped_column(String(32), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("notification_channels.id"), nullable=False)
    action_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AlertRule(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "alert_rules"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    signal: Mapped[str] = mapped_column(String(128), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("notification_channels.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class IncidentEvent(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "incident_events"

    signal: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="open", nullable=False)
    source_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class WebhookSubscription(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "webhook_subscriptions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_types_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    target_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    retry_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    permissions_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    rate_limit_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class BackupPlan(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "backup_plans"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    targets_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    schedule: Mapped[str] = mapped_column(String(255), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    rpo_seconds: Mapped[int | None] = mapped_column(Integer)
    rto_seconds: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RestoreJob(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "restore_jobs"

    backup_plan_id: Mapped[int | None] = mapped_column(ForeignKey("backup_plans.id"))
    backup_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    restore_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="created", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_report_ref: Mapped[str | None] = mapped_column(String(1024))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ReplayJob(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "replay_jobs"

    source_run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    source_agent_version_id: Mapped[int] = mapped_column(ForeignKey("agent_versions.id"))
    candidate_agent_version_id: Mapped[int] = mapped_column(
        ForeignKey("agent_versions.id"), nullable=False
    )
    replay_run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"))
    replay_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    status: Mapped[str] = mapped_column(String(64), default="created", nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(64))
    override_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AuditLog(IdMixin, AuditMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"info": {"immutable": True}}

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_id: Mapped[str | None] = mapped_column(String(64))
    actor_type: Mapped[str] = mapped_column(
        String(64), default=AuditActorType.system.value, nullable=False
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(BigInteger)
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


class ScheduledRuns(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_runs"

    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    schedule_type: Mapped[str | None] = mapped_column(String(64))
    timezone: Mapped[str] = mapped_column(String(128), default="UTC", nullable=False)
    next_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_id: Mapped[int | None] = mapped_column(BigInteger)
    last_task_id: Mapped[int | None] = mapped_column(BigInteger)
    last_run_status: Mapped[str | None] = mapped_column(String(64))
    missed_run_policy: Mapped[str] = mapped_column(String(64), default="skip", nullable=False)
    backfill_policy: Mapped[str] = mapped_column(String(64), default="none", nullable=False)
    pause_reason: Mapped[str | None] = mapped_column(String(255))
    trigger_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class BatchRuns(IdMixin, TenantProjectMixin, TimestampMixin, Base):
    __tablename__ = "batch_runs"

    status: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    deployment_id: Mapped[int | None] = mapped_column(BigInteger)
    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queued_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    running_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dead_letter_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancelled_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    partial_failure_policy: Mapped[str] = mapped_column(
        String(64),
        default="continue",
        nullable=False,
    )
    cancel_policy: Mapped[str] = mapped_column(String(64), default="queued_only", nullable=False)
    last_recomputed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


Extensions = create_metadata_model("extensions")
