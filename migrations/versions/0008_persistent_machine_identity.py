"""persistent machine identity

Revision ID: 0008_persistent_machine_identity
Revises: 0007_console_identity_sessions
Create Date: 2026-05-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_persistent_machine_identity"
down_revision: str | None = "0007_console_identity_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "service_accounts",
        sa.Column("permissions_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "api_keys",
        sa.Column("key_prefix", sa.String(length=32), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "key_prefix")
    op.drop_column("service_accounts", "permissions_json")
