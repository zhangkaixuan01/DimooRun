"""published surface evidence bundles

Revision ID: 0011_published_surface_evidence_bundles
Revises: 0010_tasks_metadata_json
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.table_helpers import audit_columns, id_column, tenant_project_columns

revision: str = "0011_published_surface_evidence_bundles"
down_revision: str | None = "0010_tasks_metadata_json"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "published_surface_evidence_bundles",
        id_column(),
        *tenant_project_columns(project_nullable=False),
        sa.Column("surface_id", sa.BigInteger(), nullable=False),
        sa.Column("bundle_id", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(128), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="recorded"),
        sa.Column("export_status", sa.String(64), nullable=False, server_default="not_exported"),
        sa.Column(
            "evidence_bundle_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "redacted_payload_summary_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("last_exported_at", sa.DateTime(timezone=True)),
        sa.Column("last_export_request_id", sa.String(255)),
        sa.Column("retention_policy_id", sa.String(128)),
        sa.Column("retain_until", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("archive_reason", sa.String(1024)),
        sa.Column("archive_request_id", sa.String(255)),
        *audit_columns(),
    )
    op.create_index(
        "ix_published_surface_evidence_bundles_tenant_id",
        "published_surface_evidence_bundles",
        ["tenant_id"],
    )
    op.create_index(
        "ix_published_surface_evidence_bundles_project_id",
        "published_surface_evidence_bundles",
        ["project_id"],
    )
    op.create_index(
        "ix_published_surface_evidence_bundles_surface_id",
        "published_surface_evidence_bundles",
        ["surface_id"],
    )
    op.create_index(
        "uq_published_surface_evidence_bundle_active",
        "published_surface_evidence_bundles",
        ["surface_id", "bundle_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_table(
        "published_surface_request_logs",
        id_column(),
        *tenant_project_columns(project_nullable=False),
        sa.Column("surface_id", sa.BigInteger(), nullable=False),
        sa.Column("request_log_id", sa.BigInteger(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("trace_id", sa.String(255)),
        sa.Column("request_id", sa.String(255)),
        sa.Column("ingress_source", sa.String(64)),
        sa.Column(
            "request_log_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "evidence_bundle_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        *audit_columns(),
    )
    op.create_index(
        "ix_published_surface_request_logs_tenant_id",
        "published_surface_request_logs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_published_surface_request_logs_project_id",
        "published_surface_request_logs",
        ["project_id"],
    )
    op.create_index(
        "ix_published_surface_request_logs_surface_id",
        "published_surface_request_logs",
        ["surface_id"],
    )
    op.create_index(
        "ix_published_surface_request_logs_request_log_id",
        "published_surface_request_logs",
        ["request_log_id"],
    )
    op.create_index(
        "ix_published_surface_request_logs_trace_id",
        "published_surface_request_logs",
        ["trace_id"],
    )
    op.create_index(
        "ix_published_surface_request_logs_request_id",
        "published_surface_request_logs",
        ["request_id"],
    )
    op.create_index(
        "uq_published_surface_request_log_active",
        "published_surface_request_logs",
        ["surface_id", "request_log_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_table(
        "published_surface_rollouts",
        id_column(),
        *tenant_project_columns(project_nullable=False),
        sa.Column("surface_id", sa.BigInteger(), nullable=False),
        sa.Column("rollout_id", sa.BigInteger(), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(255)),
        sa.Column(
            "rollout_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "evidence_bundle_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        *audit_columns(),
    )
    op.create_index(
        "ix_published_surface_rollouts_tenant_id",
        "published_surface_rollouts",
        ["tenant_id"],
    )
    op.create_index(
        "ix_published_surface_rollouts_project_id",
        "published_surface_rollouts",
        ["project_id"],
    )
    op.create_index(
        "ix_published_surface_rollouts_surface_id",
        "published_surface_rollouts",
        ["surface_id"],
    )
    op.create_index(
        "ix_published_surface_rollouts_rollout_id",
        "published_surface_rollouts",
        ["rollout_id"],
    )
    op.create_index(
        "ix_published_surface_rollouts_operation",
        "published_surface_rollouts",
        ["operation"],
    )
    op.create_index(
        "ix_published_surface_rollouts_request_id",
        "published_surface_rollouts",
        ["request_id"],
    )
    op.create_index(
        "uq_published_surface_rollout_active",
        "published_surface_rollouts",
        ["surface_id", "rollout_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_table(
        "published_surface_bindings",
        id_column(),
        *tenant_project_columns(project_nullable=False),
        sa.Column("surface_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("deployment_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(128), nullable=False),
        sa.Column("route_path", sa.String(512), nullable=False),
        sa.Column("auth_mode", sa.String(64), nullable=False),
        sa.Column("published_at", sa.String(64)),
        sa.Column(
            "surface_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        *audit_columns(),
    )
    op.create_index(
        "ix_published_surface_bindings_tenant_id",
        "published_surface_bindings",
        ["tenant_id"],
    )
    op.create_index(
        "ix_published_surface_bindings_project_id",
        "published_surface_bindings",
        ["project_id"],
    )
    op.create_index(
        "ix_published_surface_bindings_surface_id",
        "published_surface_bindings",
        ["surface_id"],
    )
    op.create_index(
        "ix_published_surface_bindings_deployment_id",
        "published_surface_bindings",
        ["deployment_id"],
    )
    op.create_index(
        "ix_published_surface_bindings_status",
        "published_surface_bindings",
        ["status"],
    )
    op.create_index(
        "ix_published_surface_bindings_environment",
        "published_surface_bindings",
        ["environment"],
    )
    op.create_index(
        "uq_published_surface_binding_active",
        "published_surface_bindings",
        ["surface_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "uq_published_surface_route_active",
        "published_surface_bindings",
        ["route_path"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_published_surface_route_active",
        table_name="published_surface_bindings",
    )
    op.drop_index(
        "uq_published_surface_binding_active",
        table_name="published_surface_bindings",
    )
    op.drop_index(
        "ix_published_surface_bindings_environment",
        table_name="published_surface_bindings",
    )
    op.drop_index(
        "ix_published_surface_bindings_status",
        table_name="published_surface_bindings",
    )
    op.drop_index(
        "ix_published_surface_bindings_deployment_id",
        table_name="published_surface_bindings",
    )
    op.drop_index(
        "ix_published_surface_bindings_surface_id",
        table_name="published_surface_bindings",
    )
    op.drop_index(
        "ix_published_surface_bindings_project_id",
        table_name="published_surface_bindings",
    )
    op.drop_index(
        "ix_published_surface_bindings_tenant_id",
        table_name="published_surface_bindings",
    )
    op.drop_table("published_surface_bindings")
    op.drop_index(
        "uq_published_surface_rollout_active",
        table_name="published_surface_rollouts",
    )
    op.drop_index(
        "ix_published_surface_rollouts_request_id",
        table_name="published_surface_rollouts",
    )
    op.drop_index(
        "ix_published_surface_rollouts_operation",
        table_name="published_surface_rollouts",
    )
    op.drop_index(
        "ix_published_surface_rollouts_rollout_id",
        table_name="published_surface_rollouts",
    )
    op.drop_index(
        "ix_published_surface_rollouts_surface_id",
        table_name="published_surface_rollouts",
    )
    op.drop_index(
        "ix_published_surface_rollouts_project_id",
        table_name="published_surface_rollouts",
    )
    op.drop_index(
        "ix_published_surface_rollouts_tenant_id",
        table_name="published_surface_rollouts",
    )
    op.drop_table("published_surface_rollouts")
    op.drop_index(
        "uq_published_surface_request_log_active",
        table_name="published_surface_request_logs",
    )
    op.drop_index(
        "ix_published_surface_request_logs_request_id",
        table_name="published_surface_request_logs",
    )
    op.drop_index(
        "ix_published_surface_request_logs_trace_id",
        table_name="published_surface_request_logs",
    )
    op.drop_index(
        "ix_published_surface_request_logs_request_log_id",
        table_name="published_surface_request_logs",
    )
    op.drop_index(
        "ix_published_surface_request_logs_surface_id",
        table_name="published_surface_request_logs",
    )
    op.drop_index(
        "ix_published_surface_request_logs_project_id",
        table_name="published_surface_request_logs",
    )
    op.drop_index(
        "ix_published_surface_request_logs_tenant_id",
        table_name="published_surface_request_logs",
    )
    op.drop_table("published_surface_request_logs")
    op.drop_index(
        "uq_published_surface_evidence_bundle_active",
        table_name="published_surface_evidence_bundles",
    )
    op.drop_index(
        "ix_published_surface_evidence_bundles_surface_id",
        table_name="published_surface_evidence_bundles",
    )
    op.drop_index(
        "ix_published_surface_evidence_bundles_project_id",
        table_name="published_surface_evidence_bundles",
    )
    op.drop_index(
        "ix_published_surface_evidence_bundles_tenant_id",
        table_name="published_surface_evidence_bundles",
    )
    op.drop_table("published_surface_evidence_bundles")
