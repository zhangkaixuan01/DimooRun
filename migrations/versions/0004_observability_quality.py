"""observability and quality tables

Revision ID: 0004_observability_quality
Revises: 0003_governance
Create Date: 2026-05-24
"""

from migrations.table_helpers import create_placeholder_table, drop_tables

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
    for table_name in TABLE_NAMES:
        create_placeholder_table(table_name)


def downgrade() -> None:
    drop_tables(TABLE_NAMES)
