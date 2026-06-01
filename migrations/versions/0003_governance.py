"""governance tables

Revision ID: 0003_governance
Revises: 0002_runtime_execution
Create Date: 2026-05-24
"""

from alembic import op
from sqlalchemy import BigInteger, JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, text

from migrations.table_helpers import audit_columns, drop_tables, id_column, tenant_project_columns

revision = "0003_governance"
down_revision = "0002_runtime_execution"
branch_labels = None
depends_on = None

TABLE_NAMES = (
    "policies",
    "policy_decisions",
    "tools",
    "secrets",
    "execution_profiles",
    "model_gateways",
    "model_policies",
    "model_usage_snapshots",
    "human_tasks",
    "approval_requests",
    "approval_policies",
)


def upgrade() -> None:
    op.create_table(
        "policies",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("type", String(128), nullable=False),
        Column("resource_type", String(128), nullable=False),
        Column("action", String(128), nullable=False),
        Column("decision", String(64), nullable=False),
        Column("priority", Integer, nullable=False, server_default="100"),
        Column("risk_level", String(64)),
        Column("condition_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("reason", String(255)),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "policy_decisions",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("policy_id", BigInteger, ForeignKey("policies.id")),
        Column("resource_type", String(128), nullable=False),
        Column("resource_id", BigInteger),
        Column("action", String(128), nullable=False),
        Column("decision", String(64), nullable=False),
        Column("reason", String(255)),
        Column("actor_id", String(64)),
        Column("actor_type", String(64)),
        Column("matched_policy_ids_json", JSON, nullable=False, server_default=text("'[]'")),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "tools",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("name", String(255), nullable=False),
        Column("description", String),
        Column("schema_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("risk_level", String(64), nullable=False, server_default="read"),
        Column("status", String(64), nullable=False, server_default="active"),
        *audit_columns(),
    )
    op.create_table(
        "secrets",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id"), nullable=False),
        Column("name", String(255), nullable=False),
        Column("provider", String(128), nullable=False),
        Column("scope", String(128), nullable=False),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("last_used_at", DateTime(timezone=True)),
        *audit_columns(),
    )
    op.create_table(
        "execution_profiles",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("name", String(255), nullable=False),
        Column("isolation_level", String(64), nullable=False),
        Column("image", String(512)),
        Column("python_version", String(64)),
        Column("dependency_lock_required", Boolean, nullable=False, server_default="1"),
        Column("network_policy", String(128), nullable=False),
        Column("filesystem_policy", String(128), nullable=False),
        Column("cpu_limit", String(64)),
        Column("memory_limit", String(64)),
        Column("timeout_seconds", Integer),
        Column("allowed_env_json", JSON, nullable=False, server_default=text("'[]'")),
        Column("allowed_secret_refs_json", JSON, nullable=False, server_default=text("'[]'")),
        Column("allowed_gateway_refs_json", JSON, nullable=False, server_default=text("'[]'")),
        Column("status", String(64), nullable=False, server_default="active"),
        *audit_columns(),
    )
    op.create_index(
        "uq_execution_profiles_scope_name_active",
        "execution_profiles",
        ["tenant_id", "project_id", "name"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "model_gateways",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("name", String(255), nullable=False),
        Column("provider_type", String(64), nullable=False),
        Column("base_url", String(1024), nullable=False),
        Column("credential_ref", String(512), nullable=False),
        Column("default_model_group", String(255)),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_index(
        "uq_model_gateways_scope_name_active",
        "model_gateways",
        ["tenant_id", "project_id", "name"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "model_policies",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("agent_id", BigInteger, ForeignKey("agents.id")),
        Column("agent_version_id", BigInteger, ForeignKey("agent_versions.id")),
        Column("gateway_id", BigInteger, ForeignKey("model_gateways.id"), nullable=False),
        Column("allowed_models_json", JSON, nullable=False, server_default=text("'[]'")),
        Column("denied_models_json", JSON, nullable=False, server_default=text("'[]'")),
        Column("default_model", String(255), nullable=False),
        Column("max_tokens_per_run", Integer),
        Column("max_cost_per_run", Float),
        Column("max_cost_per_day", Float),
        Column("fallback_policy_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("on_budget_exceeded", String(64), nullable=False),
        Column("status", String(64), nullable=False, server_default="active"),
        *audit_columns(),
    )
    op.create_table(
        "model_usage_snapshots",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id")),
        Column("run_id", BigInteger, ForeignKey("runs.id"), nullable=False),
        Column("attempt_id", BigInteger, ForeignKey("run_attempts.id")),
        Column("gateway_id", BigInteger, ForeignKey("model_gateways.id"), nullable=False),
        Column("gateway_request_id", String(255)),
        Column("model", String(255), nullable=False),
        Column("provider", String(128)),
        Column("prompt_tokens", Integer, nullable=False, server_default="0"),
        Column("completion_tokens", Integer, nullable=False, server_default="0"),
        Column("total_tokens", Integer, nullable=False, server_default="0"),
        Column("cost", Float, nullable=False, server_default="0"),
        Column("currency", String(16), nullable=False, server_default="USD"),
        Column("raw_usage_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "human_tasks",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("run_id", BigInteger, ForeignKey("runs.id")),
        Column("attempt_id", BigInteger, ForeignKey("run_attempts.id")),
        Column("task_id", BigInteger, ForeignKey("tasks.id")),
        Column("type", String(64), nullable=False),
        Column("status", String(64), nullable=False, server_default="pending"),
        Column("assignee_user_id", BigInteger, ForeignKey("users.id")),
        Column("assignee_role", String(128)),
        Column("payload_ref", String(1024)),
        Column("decision_ref", String(1024)),
        Column("expires_at", DateTime(timezone=True)),
        *audit_columns(),
    )
    op.create_table(
        "approval_requests",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("human_task_id", BigInteger, ForeignKey("human_tasks.id"), nullable=False),
        Column("requested_by", String(64)),
        Column("status", String(64), nullable=False, server_default="pending"),
        Column("decision_ref", String(1024)),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "approval_policies",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("name", String(255), nullable=False),
        Column("resource_type", String(128), nullable=False),
        Column("action", String(128), nullable=False),
        Column("risk_level", String(64)),
        Column("condition_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("required_role", String(128), nullable=False),
        Column("timeout_seconds", Integer),
        Column("on_timeout", String(64), nullable=False),
        Column("status", String(64), nullable=False, server_default="active"),
        *audit_columns(),
    )


def downgrade() -> None:
    drop_tables(TABLE_NAMES)
