"""platform extension tables

Revision ID: 0005_platform_extensions
Revises: 0004_observability_quality
Create Date: 2026-05-24
"""

from migrations.table_helpers import create_placeholder_table, drop_tables

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
    for table_name in TABLE_NAMES:
        create_placeholder_table(table_name)


def downgrade() -> None:
    drop_tables(TABLE_NAMES)
