"""platform control settings

Revision ID: 0009_platform_control_settings
Revises: 0008_persistent_machine_identity
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.table_helpers import audit_columns, drop_tables, id_column, tenant_project_columns

revision: str = "0009_platform_control_settings"
down_revision: str | None = "0008_persistent_machine_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAMES = (
    "observability_exporters",
    "sandbox_policies",
    "container_pool_policies",
)


def upgrade() -> None:
    op.create_table(
        "observability_exporters",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("exporter_type", sa.String(64), nullable=False),
        sa.Column("target_ref", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "sandbox_policies",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("isolation_level", sa.String(64), nullable=False, server_default="process"),
        sa.Column("network_policy", sa.String(128), nullable=False, server_default="deny_all"),
        sa.Column("filesystem_policy", sa.String(128), nullable=False, server_default="read_only"),
        sa.Column("status", sa.String(64), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "container_pool_policies",
        id_column(),
        *tenant_project_columns(project_nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("max_containers", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("cpu_limit", sa.String(64), nullable=False, server_default="1000m"),
        sa.Column("memory_limit", sa.String(64), nullable=False, server_default="1Gi"),
        sa.Column("idle_timeout_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("status", sa.String(64), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *audit_columns(),
    )


def downgrade() -> None:
    drop_tables(TABLE_NAMES)
