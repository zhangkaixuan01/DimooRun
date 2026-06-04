"""add task metadata json

Revision ID: 0010_tasks_metadata_json
Revises: 0009_platform_control_settings
Create Date: 2026-06-01
"""

from alembic import op
from sqlalchemy import JSON, Column, inspect, text

revision = "0010_tasks_metadata_json"
down_revision = "0009_platform_control_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("tasks")}
    if "metadata_json" not in columns:
        op.add_column(
            "tasks",
            Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        )
    indexes = {index["name"] for index in inspect(bind).get_indexes("api_keys")}
    if "ix_api_keys_owner_id" not in indexes:
        op.create_index("ix_api_keys_owner_id", "api_keys", ["owner_id"])


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {index["name"] for index in inspect(bind).get_indexes("api_keys")}
    if "ix_api_keys_owner_id" in indexes:
        op.drop_index("ix_api_keys_owner_id", table_name="api_keys")
    columns = {column["name"] for column in inspect(bind).get_columns("tasks")}
    if "metadata_json" in columns:
        op.drop_column("tasks", "metadata_json")
