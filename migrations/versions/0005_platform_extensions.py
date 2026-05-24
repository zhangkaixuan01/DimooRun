"""platform extension tables

Revision ID: 0005_platform_extensions
Revises: 0004_observability_quality
Create Date: 2026-05-24
"""

from alembic import op
from dimoo_run.domain import models  # noqa: F401
from dimoo_run.persistence.database import Base

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
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[name] for name in TABLE_NAMES])


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLE_NAMES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
