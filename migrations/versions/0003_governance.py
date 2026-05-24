"""governance tables

Revision ID: 0003_governance
Revises: 0002_runtime_execution
Create Date: 2026-05-24
"""

from alembic import op
from dimoo_run.domain import models  # noqa: F401
from dimoo_run.persistence.database import Base

revision = "0003_governance"
down_revision = "0002_runtime_execution"
branch_labels = None
depends_on = None

TABLE_NAMES = (
    "policies",
    "policy_decisions",
    "tools",
    "secrets",
    "model_gateways",
    "model_policies",
    "model_usage_snapshots",
    "human_tasks",
    "approval_requests",
    "approval_policies",
)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[name] for name in TABLE_NAMES])


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLE_NAMES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
