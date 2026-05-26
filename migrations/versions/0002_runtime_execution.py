"""runtime execution tables

Revision ID: 0002_runtime_execution
Revises: 0001_core_identity_and_agents
Create Date: 2026-05-24
"""

from alembic import op
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)

from migrations.table_helpers import (
    audit_columns,
    drop_tables,
    id_column,
)

revision = "0002_runtime_execution"
down_revision = "0001_core_identity_and_agents"
branch_labels = None
depends_on = None

TABLE_NAMES = (
    "sessions",
    "runs",
    "tasks",
    "run_attempts",
    "events",
    "checkpoint_indexes",
    "artifacts",
    "audit_logs",
    "idempotency_records",
)


def upgrade() -> None:
    op.create_table(
        "sessions",
        id_column(),
        Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
        Column("project_id", String(64), ForeignKey("projects.id"), nullable=False),
        Column("user_id", String(64), ForeignKey("users.id")),
        Column("service_account_id", String(64), ForeignKey("service_accounts.id")),
        Column("agent_id", String(64), ForeignKey("agents.id"), nullable=False),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "runs",
        id_column(),
        Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
        Column("project_id", String(64), ForeignKey("projects.id"), nullable=False),
        Column("user_id", String(64), ForeignKey("users.id")),
        Column("service_account_id", String(64), ForeignKey("service_accounts.id")),
        Column("agent_id", String(64), ForeignKey("agents.id"), nullable=False),
        Column("agent_version_id", String(64), ForeignKey("agent_versions.id"), nullable=False),
        Column("deployment_id", String(64), ForeignKey("deployments.id")),
        Column("session_id", String(64), ForeignKey("sessions.id")),
        Column("framework", String(128)),
        Column("adapter", String(128)),
        Column("thread_id", String(255)),
        Column("trace_id", String(255)),
        Column("idempotency_key", String(255)),
        Column("status", String(64), nullable=False, server_default="pending"),
        Column("input_ref", String(1024)),
        Column("output_ref", String(1024)),
        Column("error", Text),
        Column("started_at", DateTime(timezone=True)),
        Column("finished_at", DateTime(timezone=True)),
        *audit_columns(),
    )
    op.create_index("ix_runs_tenant_id", "runs", ["tenant_id"])
    op.create_index("ix_runs_project_id", "runs", ["project_id"])
    op.create_index("ix_runs_idempotency_key", "runs", ["idempotency_key"])
    op.create_table(
        "tasks",
        id_column(),
        Column("run_id", String(64), ForeignKey("runs.id"), nullable=False),
        Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
        Column("project_id", String(64), ForeignKey("projects.id"), nullable=False),
        Column("status", String(64), nullable=False, server_default="queued"),
        Column("attempt", Integer, nullable=False, server_default="0"),
        Column("max_attempts", Integer, nullable=False, server_default="3"),
        Column("queue", String(128), nullable=False, server_default="default"),
        Column("priority", Integer, nullable=False, server_default="0"),
        Column("scheduled_at", DateTime(timezone=True)),
        Column("started_at", DateTime(timezone=True)),
        Column("finished_at", DateTime(timezone=True)),
        Column("leased_until", DateTime(timezone=True)),
        Column("worker_id", String(128)),
        Column("heartbeat_at", DateTime(timezone=True)),
        Column("fencing_token", Integer, nullable=False, server_default="0"),
        Column("dedupe_key", String(255)),
        Column("idempotency_key", String(255)),
        Column("error", Text),
        Column("dead_letter_reason", Text),
        *audit_columns(),
    )
    op.create_table(
        "run_attempts",
        id_column(),
        Column("run_id", String(64), ForeignKey("runs.id"), nullable=False),
        Column("task_id", String(64), ForeignKey("tasks.id")),
        Column("attempt_no", Integer, nullable=False),
        Column("worker_id", String(128)),
        Column("status", String(64), nullable=False, server_default="running"),
        Column("started_at", DateTime(timezone=True)),
        Column("finished_at", DateTime(timezone=True)),
        Column("error", Text),
        Column("latency_ms", Integer),
        *audit_columns(),
    )
    op.create_table(
        "events",
        id_column(),
        Column("run_id", String(64), ForeignKey("runs.id"), nullable=False),
        Column("attempt_id", String(64), ForeignKey("run_attempts.id")),
        Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
        Column("project_id", String(64), ForeignKey("projects.id"), nullable=False),
        Column("type", String(128), nullable=False),
        Column("sequence", Integer, nullable=False),
        Column("event_id", String(512), nullable=False),
        Column("framework", String(128)),
        Column("payload_ref", String(1024)),
        Column("payload_json", JSON),
        Column("visibility_level", String(64), nullable=False, server_default="internal"),
        *audit_columns(),
        UniqueConstraint("run_id", "sequence", name="uq_events_run_sequence"),
    )
    op.create_index("ix_events_event_id", "events", ["event_id"])
    op.create_table(
        "checkpoint_indexes",
        id_column(),
        Column("run_id", String(64), ForeignKey("runs.id"), nullable=False),
        Column("thread_id", String(255), nullable=False),
        Column("checkpoint_ns", String(255)),
        Column("checkpoint_id", String(255), nullable=False),
        Column("payload_uri", String(1024), nullable=False),
        *audit_columns(),
    )
    op.create_table(
        "artifacts",
        id_column(),
        Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
        Column("project_id", String(64), ForeignKey("projects.id")),
        Column("run_id", String(64), ForeignKey("runs.id")),
        Column("attempt_id", String(64), ForeignKey("run_attempts.id")),
        Column("event_id", String(512)),
        Column("artifact_type", String(128), nullable=False),
        Column("mime_type", String(128), nullable=False),
        Column("size_bytes", Integer, nullable=False),
        Column("storage_uri", String(1024), nullable=False),
        Column("checksum", String(255), nullable=False),
        Column("visibility_level", String(64), nullable=False, server_default="internal"),
        Column("retention_policy_id", String(64)),
        Column("expires_at", DateTime(timezone=True)),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "audit_logs",
        id_column(),
        Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
        Column("project_id", String(64), ForeignKey("projects.id")),
        Column("actor_user_id", String(64), ForeignKey("users.id")),
        Column("actor_id", String(64)),
        Column("actor_type", String(64), nullable=False, server_default="system"),
        Column("action", String(128), nullable=False),
        Column("resource_type", String(128), nullable=False),
        Column("resource_id", String(64)),
        Column("result", String(64), nullable=False),
        Column("ip", String(128)),
        Column("user_agent", String(512)),
        Column("request_id", String(255)),
        Column("trace_id", String(255)),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "idempotency_records",
        id_column(),
        Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
        Column("project_id", String(64), ForeignKey("projects.id")),
        Column("endpoint", String(512), nullable=False),
        Column("idempotency_key", String(255), nullable=False),
        Column("request_hash", String(255), nullable=False),
        Column("response_ref", String(1024)),
        Column("status", String(64), nullable=False, server_default="pending"),
        Column("expires_at", DateTime(timezone=True)),
        *audit_columns(),
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "endpoint",
            "idempotency_key",
            name="uq_idempotency_records_scope_key",
        ),
    )


def downgrade() -> None:
    drop_tables(TABLE_NAMES)
