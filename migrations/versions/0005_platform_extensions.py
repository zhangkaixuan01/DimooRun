"""platform extension tables

Revision ID: 0005_platform_extensions
Revises: 0004_observability_quality
Create Date: 2026-05-24
"""

from alembic import op
from sqlalchemy import BigInteger, JSON, Boolean, Column, Float, ForeignKey, String, text

from migrations.table_helpers import (
    audit_columns,
    create_placeholder_table,
    drop_tables,
    id_column,
    tenant_project_columns,
)

revision = "0005_platform_extensions"
down_revision = "0004_observability_quality"
branch_labels = None
depends_on = None

TABLE_NAMES = (
    "published_surfaces",
    "ingress_routes",
    "catalog_items",
    "prompt_assets",
    "config_assets",
    "templates",
    "scheduled_runs",
    "batch_runs",
    "replay_jobs",
    "notification_channels",
    "alert_rules",
    "incident_events",
    "webhook_subscriptions",
    "extensions",
    "backup_plans",
    "restore_jobs",
)


def upgrade() -> None:
    op.create_table(
        "published_surfaces",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id"), nullable=False),
        Column("deployment_id", BigInteger, ForeignKey("deployments.id"), nullable=False),
        Column("type", String(64), nullable=False),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_index("ix_published_surfaces_tenant_id", "published_surfaces", ["tenant_id"])
    op.create_index("ix_published_surfaces_project_id", "published_surfaces", ["project_id"])
    op.create_index(
        "uq_published_surfaces_deployment_type_active",
        "published_surfaces",
        ["deployment_id", "type"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "ingress_routes",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id"), nullable=False),
        Column("surface_id", BigInteger, ForeignKey("published_surfaces.id"), nullable=False),
        Column("path", String(512), nullable=False),
        Column("custom_domain", String(255)),
        Column("auth_mode", String(64), nullable=False),
        Column("cors_policy_id", String(64)),
        Column("rate_limit_policy_id", String(64)),
        Column("request_transform_ref", String(1024)),
        Column("response_transform_ref", String(1024)),
        Column("access_log_enabled", Boolean, nullable=False, server_default="1"),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_index("ix_ingress_routes_tenant_id", "ingress_routes", ["tenant_id"])
    op.create_index("ix_ingress_routes_project_id", "ingress_routes", ["project_id"])
    op.create_index(
        "uq_ingress_routes_surface_path_active",
        "ingress_routes",
        ["surface_id", "path"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "catalog_items",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("type", String(128), nullable=False),
        Column("name", String(255), nullable=False),
        Column("provider", String(255), nullable=False),
        Column("version", String(128), nullable=False),
        Column("schema_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("capabilities_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("risk_level", String(64), nullable=False),
        Column("required_secrets_json", JSON, nullable=False, server_default=text("'[]'")),
        Column("required_permissions_json", JSON, nullable=False, server_default=text("'[]'")),
        Column("runtime_requirements_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("status", String(64), nullable=False, server_default="active"),
        *audit_columns(),
    )
    op.create_index(
        "uq_catalog_items_scope_type_name_version_active",
        "catalog_items",
        ["tenant_id", "project_id", "type", "name", "version"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "prompt_assets",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("name", String(255), nullable=False),
        Column("version", String(128), nullable=False),
        Column("content_ref", String(1024), nullable=False),
        Column("variables_schema_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("visibility_level", String(64), nullable=False, server_default="internal"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_index(
        "uq_prompt_assets_scope_name_version_active",
        "prompt_assets",
        ["tenant_id", "project_id", "name", "version"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "config_assets",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("name", String(255), nullable=False),
        Column("version", String(128), nullable=False),
        Column("schema_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("content_ref", String(1024), nullable=False),
        Column("environment", String(128)),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_index(
        "uq_config_assets_scope_name_version_active",
        "config_assets",
        ["tenant_id", "project_id", "name", "version"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "templates",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("type", String(128), nullable=False),
        Column("name", String(255), nullable=False),
        Column("version", String(128), nullable=False),
        Column("content_ref", String(1024), nullable=False),
        Column("schema_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_index(
        "uq_templates_scope_type_name_version_active",
        "templates",
        ["tenant_id", "project_id", "type", "name", "version"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "replay_jobs",
        id_column(),
        *tenant_project_columns(),
        Column("source_run_id", BigInteger, ForeignKey("runs.id"), nullable=False),
        Column("source_agent_version_id", BigInteger, ForeignKey("agent_versions.id")),
        Column(
            "candidate_agent_version_id",
            BigInteger,
            ForeignKey("agent_versions.id"),
            nullable=False,
        ),
        Column("replay_run_id", BigInteger, ForeignKey("runs.id")),
        Column("replay_task_id", BigInteger, ForeignKey("tasks.id")),
        Column("status", String(64), nullable=False, server_default="created"),
        Column("requested_by", String(64)),
        Column("override_config_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "notification_channels",
        id_column(),
        *tenant_project_columns(),
        Column("type", String(64), nullable=False),
        Column("target_ref", String(512), nullable=False),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "alert_rules",
        id_column(),
        *tenant_project_columns(),
        Column("name", String(255), nullable=False),
        Column("signal", String(128), nullable=False),
        Column("threshold", Float, nullable=False),
        Column("channel_id", BigInteger, ForeignKey("notification_channels.id"), nullable=False),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "incident_events",
        id_column(),
        *tenant_project_columns(),
        Column("signal", String(128), nullable=False),
        Column("severity", String(64), nullable=False),
        Column("status", String(64), nullable=False, server_default="open"),
        Column("source_ref", String(1024), nullable=False),
        Column("value", Float, nullable=False),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    for table_name in [
        "scheduled_runs",
        "batch_runs",
        "webhook_subscriptions",
        "extensions",
        "backup_plans",
        "restore_jobs",
    ]:
        create_placeholder_table(table_name)


def downgrade() -> None:
    drop_tables(TABLE_NAMES)
