"""governance tables

Revision ID: 0003_governance
Revises: 0002_runtime_execution
Create Date: 2026-05-24
"""

from migrations.table_helpers import create_named_stub_table, create_placeholder_table, drop_tables

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
    create_named_stub_table("tools")
    create_named_stub_table("secrets")
    for table_name in (
        "policies",
        "policy_decisions",
        "model_gateways",
        "model_policies",
        "model_usage_snapshots",
        "human_tasks",
        "approval_requests",
        "approval_policies",
    ):
        create_placeholder_table(table_name)


def downgrade() -> None:
    drop_tables(TABLE_NAMES)
