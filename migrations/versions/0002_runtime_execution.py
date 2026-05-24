"""runtime execution tables

Revision ID: 0002_runtime_execution
Revises: 0001_core_identity_and_agents
Create Date: 2026-05-24
"""

from alembic import op
from dimoo_run.domain import models  # noqa: F401
from dimoo_run.persistence.database import Base

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
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[name] for name in TABLE_NAMES])


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLE_NAMES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
