"""core identity and agent tables

Revision ID: 0001_core_identity_and_agents
Revises:
Create Date: 2026-05-24
"""

from alembic import op
from dimoo_run.domain import models  # noqa: F401
from dimoo_run.persistence.database import Base

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
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[name] for name in TABLE_NAMES])


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLE_NAMES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
