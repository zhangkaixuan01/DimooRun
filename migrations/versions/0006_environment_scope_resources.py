"""environment scope resources

Revision ID: 0006_environment_scope_resources
Revises: 0005_platform_extensions
Create Date: 2026-05-27
"""

from alembic import op
from sqlalchemy import BigInteger, JSON, Column, ForeignKey, String, UniqueConstraint, text

from migrations.table_helpers import audit_columns, drop_tables, id_column

revision = "0006_environment_scope_resources"
down_revision = "0005_platform_extensions"
branch_labels = None
depends_on = None

TABLE_NAMES = ("environments",)


def upgrade() -> None:
    op.create_table(
        "environments",
        id_column(),
        Column("tenant_id", BigInteger, ForeignKey("tenants.id"), nullable=False),
        Column("project_id", BigInteger, ForeignKey("projects.id"), nullable=False),
        Column("name", String(255), nullable=False),
        Column("environment", String(128), nullable=False),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "environment",
            name="uq_environments_project_environment",
        ),
    )
    op.create_index("ix_environments_tenant_id", "environments", ["tenant_id"])
    op.create_index("ix_environments_project_id", "environments", ["project_id"])


def downgrade() -> None:
    drop_tables(TABLE_NAMES)
