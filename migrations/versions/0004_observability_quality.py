"""observability and quality tables

Revision ID: 0004_observability_quality
Revises: 0003_governance
Create Date: 2026-05-24
"""

from alembic import op
from dimoo_run.domain import models  # noqa: F401
from dimoo_run.persistence.database import Base

revision = "0004_observability_quality"
down_revision = "0003_governance"
branch_labels = None
depends_on = None

TABLE_NAMES = (
    "run_graph_nodes",
    "run_graph_edges",
    "datasets",
    "dataset_items",
    "experiments",
    "experiment_runs",
    "evaluation_results",
    "feedback",
    "memory_blocks",
    "semantic_store_providers",
)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[name] for name in TABLE_NAMES])


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLE_NAMES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
