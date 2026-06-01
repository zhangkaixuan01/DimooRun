"""core identity and agent tables

Revision ID: 0001_core_identity_and_agents
Revises:
Create Date: 2026-05-24
"""

from alembic import op
from sqlalchemy import (
    BigInteger,
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

from migrations.table_helpers import audit_columns, drop_tables, id_column, integer_column

revision = "0001_core_identity_and_agents"
down_revision = None
branch_labels = None
depends_on = None

TABLE_NAMES = (
    "tenants",
    "projects",
    "users",
    "service_accounts",
    "roles",
    "permissions",
    "api_keys",
    "agents",
    "agent_versions",
    "deployments",
    "agent_instances",
)


def upgrade() -> None:
    op.create_table(
        "tenants",
        id_column(),
        Column("name", String(255), nullable=False),
        Column("slug", String(255), nullable=False, unique=True),
        Column("status", String(64), nullable=False, server_default="active"),
        *audit_columns(),
    )
    op.create_table(
        "projects",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("name", String(255), nullable=False),
        Column("slug", String(255), nullable=False),
        Column("status", String(64), nullable=False, server_default="active"),
        *audit_columns(),
        UniqueConstraint("tenant_id", "slug", name="uq_projects_tenant_slug"),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_table(
        "users",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("email", String(320), nullable=False),
        Column("name", String(255)),
        Column("status", String(64), nullable=False, server_default="active"),
        *audit_columns(),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_table(
        "service_accounts",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id")),
        Column("name", String(255), nullable=False),
        Column("description", Text),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("last_used_at", DateTime(timezone=True)),
        *audit_columns(),
    )
    op.create_index("ix_service_accounts_tenant_id", "service_accounts", ["tenant_id"])
    op.create_index("ix_service_accounts_project_id", "service_accounts", ["project_id"])
    op.create_table(
        "roles",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id")),
        Column("name", String(255), nullable=False),
        Column("description", Text),
        Column("status", String(64), nullable=False, server_default="active"),
        *audit_columns(),
    )
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])
    op.create_index("ix_roles_project_id", "roles", ["project_id"])
    op.create_table(
        "permissions",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id")),
        Column("resource", String(128), nullable=False),
        Column("action", String(128), nullable=False),
        Column("name", String(255), nullable=False),
        *audit_columns(),
    )
    op.create_index("ix_permissions_tenant_id", "permissions", ["tenant_id"])
    op.create_index("ix_permissions_project_id", "permissions", ["project_id"])
    op.create_table(
        "api_keys",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id")),
        Column("name", String(255), nullable=False),
        Column("owner_type", String(64), nullable=False),
        Column("owner_id", BigInteger, ForeignKey("service_accounts.id"), nullable=False),
        Column("key_hash", String(255), nullable=False),
        Column("scopes_json", JSON, nullable=False, server_default=text("'[]'")),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("last_used_at", DateTime(timezone=True)),
        Column("rotation_policy_json", JSON),
        Column("expires_at", DateTime(timezone=True)),
        *audit_columns(),
        UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])
    op.create_table(
        "agents",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id"), nullable=False),
        Column("name", String(255), nullable=False),
        Column("description", Text),
        Column("owner_id", BigInteger, ForeignKey("users.id")),
        Column("status", String(64), nullable=False, server_default="active"),
        *audit_columns(),
    )
    op.create_index("ix_agents_tenant_id", "agents", ["tenant_id"])
    op.create_index("ix_agents_project_id", "agents", ["project_id"])
    op.create_index(
        "uq_agents_project_name_active",
        "agents",
        ["project_id", "name"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "agent_versions",
        id_column(),
        Column("agent_id", BigInteger, ForeignKey("agents.id"), nullable=False),
        Column("version", String(128), nullable=False),
        Column("package_uri", String(1024), nullable=False),
        Column("framework", String(128), nullable=False),
        Column("adapter", String(128), nullable=False),
        Column("capabilities_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("entrypoint", String(512), nullable=False),
        Column("manifest_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("adapter_api_version", String(64)),
        Column("framework_version", String(128)),
        Column("manifest_schema_version", String(64)),
        Column("capability_schema_version", String(64)),
        Column("event_schema_version", String(64)),
        Column("compatibility_status", String(64)),
        Column("compatibility_checked_at", DateTime(timezone=True)),
        Column("status", String(64), nullable=False, server_default="draft"),
        *audit_columns(),
        UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
    )
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])
    op.create_table(
        "deployments",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id"), nullable=False),
        Column("agent_id", BigInteger, ForeignKey("agents.id"), nullable=False),
        Column("agent_version_id", BigInteger, ForeignKey("agent_versions.id"), nullable=False),
        Column("environment", String(128), nullable=False),
        Column("desired_status", String(64), nullable=False, server_default="draft"),
        Column("runtime_status", String(64), nullable=False, server_default="not_loaded"),
        Column("replicas", Integer, nullable=False, server_default="1"),
        Column("config_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("last_runtime_error", Text),
        *audit_columns(),
    )
    op.create_index("ix_deployments_tenant_id", "deployments", ["tenant_id"])
    op.create_index("ix_deployments_project_id", "deployments", ["project_id"])
    op.create_index("ix_deployments_agent_id", "deployments", ["agent_id"])
    op.create_index("ix_deployments_agent_version_id", "deployments", ["agent_version_id"])
    op.create_index(
        "uq_deployments_project_environment_agent_active",
        "deployments",
        ["project_id", "environment", "agent_id"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "agent_instances",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id"), nullable=False),
        Column("deployment_id", BigInteger, ForeignKey("deployments.id"), nullable=False),
        Column("agent_id", BigInteger, ForeignKey("agents.id"), nullable=False),
        Column("agent_version_id", BigInteger, ForeignKey("agent_versions.id"), nullable=False),
        Column("worker_id", String(128), nullable=False),
        Column("execution_profile_id", String(128)),
        Column("cache_key", String(512), nullable=False),
        Column("status", String(64), nullable=False, server_default="loading"),
        Column("loaded_at", DateTime(timezone=True)),
        Column("last_used_at", DateTime(timezone=True)),
        Column("heartbeat_at", DateTime(timezone=True)),
        integer_column("running_runs", "0"),
        Column("error", Text),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_index("ix_agent_instances_tenant_id", "agent_instances", ["tenant_id"])
    op.create_index("ix_agent_instances_project_id", "agent_instances", ["project_id"])


def downgrade() -> None:
    drop_tables(TABLE_NAMES)
