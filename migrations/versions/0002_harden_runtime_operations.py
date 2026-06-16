"""harden runtime operations

Revision ID: 0002_harden_runtime_operations
Revises: 0001_baseline
Create Date: 2026-06-15 15:45:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_harden_runtime_operations"
down_revision: str | Sequence[str] | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "scheduled_runs",
        sa.Column("schedule_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "scheduled_runs",
        sa.Column("timezone", sa.String(length=128), nullable=False, server_default="UTC"),
    )
    op.add_column(
        "scheduled_runs",
        sa.Column("next_fire_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "scheduled_runs",
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("scheduled_runs", sa.Column("last_run_id", sa.BigInteger(), nullable=True))
    op.add_column("scheduled_runs", sa.Column("last_task_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "scheduled_runs",
        sa.Column("last_run_status", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "scheduled_runs",
        sa.Column(
            "missed_run_policy",
            sa.String(length=64),
            nullable=False,
            server_default="skip",
        ),
    )
    op.add_column(
        "scheduled_runs",
        sa.Column(
            "backfill_policy",
            sa.String(length=64),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "scheduled_runs",
        sa.Column("pause_reason", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "scheduled_runs",
        sa.Column("trigger_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column("batch_runs", sa.Column("deployment_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "batch_runs",
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "batch_runs",
        sa.Column("queued_items", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "batch_runs",
        sa.Column("running_items", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "batch_runs",
        sa.Column("completed_items", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "batch_runs",
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "batch_runs",
        sa.Column("dead_letter_items", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "batch_runs",
        sa.Column("cancelled_items", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "batch_runs",
        sa.Column(
            "partial_failure_policy",
            sa.String(length=64),
            nullable=False,
            server_default="continue",
        ),
    )
    op.add_column(
        "batch_runs",
        sa.Column(
            "cancel_policy",
            sa.String(length=64),
            nullable=False,
            server_default="queued_only",
        ),
    )
    op.add_column(
        "batch_runs",
        sa.Column("last_recomputed_at", sa.DateTime(timezone=True), nullable=True),
    )

    _backfill_runtime_operation_columns()


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("batch_runs") as batch_op:
        batch_op.drop_column("last_recomputed_at")
        batch_op.drop_column("cancel_policy")
        batch_op.drop_column("partial_failure_policy")
        batch_op.drop_column("cancelled_items")
        batch_op.drop_column("dead_letter_items")
        batch_op.drop_column("failed_items")
        batch_op.drop_column("completed_items")
        batch_op.drop_column("running_items")
        batch_op.drop_column("queued_items")
        batch_op.drop_column("total_items")
        batch_op.drop_column("deployment_id")

    with op.batch_alter_table("scheduled_runs") as batch_op:
        batch_op.drop_column("trigger_count")
        batch_op.drop_column("pause_reason")
        batch_op.drop_column("backfill_policy")
        batch_op.drop_column("missed_run_policy")
        batch_op.drop_column("last_run_status")
        batch_op.drop_column("last_task_id")
        batch_op.drop_column("last_run_id")
        batch_op.drop_column("last_triggered_at")
        batch_op.drop_column("next_fire_at")
        batch_op.drop_column("timezone")
        batch_op.drop_column("schedule_type")


def _backfill_runtime_operation_columns() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()

    scheduled_runs = sa.Table("scheduled_runs", metadata, autoload_with=bind)
    batch_runs = sa.Table("batch_runs", metadata, autoload_with=bind)

    for row in bind.execute(sa.select(scheduled_runs.c.id, scheduled_runs.c.metadata_json)):
        payload = _coerce_json(row.metadata_json)
        bind.execute(
            scheduled_runs.update()
            .where(scheduled_runs.c.id == row.id)
            .values(
                schedule_type=_clean_string(payload.get("schedule_type")),
                timezone=_clean_string(payload.get("timezone")) or "UTC",
                next_fire_at=_clean_string(payload.get("next_fire_time")),
                last_triggered_at=_clean_string(payload.get("last_triggered_at")),
                last_run_id=_coerce_int(payload.get("last_run_id")),
                last_task_id=_coerce_int(payload.get("last_task_id")),
                last_run_status=_clean_string(payload.get("last_run_status")),
                missed_run_policy=_clean_string(payload.get("missed_run_policy")) or "skip",
                backfill_policy=_clean_string(payload.get("backfill_policy")) or "none",
                pause_reason=_clean_string(payload.get("pause_reason")),
                trigger_count=_coerce_int(payload.get("trigger_count")) or 0,
            )
        )

    for row in bind.execute(sa.select(batch_runs.c.id, batch_runs.c.metadata_json)):
        payload = _coerce_json(row.metadata_json)
        progress_value = payload.get("progress_summary")
        progress = progress_value if isinstance(progress_value, dict) else {}
        bind.execute(
            batch_runs.update()
            .where(batch_runs.c.id == row.id)
            .values(
                deployment_id=_coerce_int(payload.get("deployment_id")),
                total_items=_coerce_int(progress.get("total_items")) or 0,
                queued_items=_coerce_int(progress.get("queued_items")) or 0,
                running_items=_coerce_int(progress.get("running_items")) or 0,
                completed_items=_coerce_int(progress.get("completed_items")) or 0,
                failed_items=_coerce_int(progress.get("failed_items")) or 0,
                dead_letter_items=_coerce_int(progress.get("dead_letter_items")) or 0,
                cancelled_items=_coerce_int(progress.get("cancelled_items")) or 0,
                partial_failure_policy=_clean_string(payload.get("partial_failure_policy"))
                or "continue",
                cancel_policy=_clean_string(payload.get("cancel_policy")) or "queued_only",
                last_recomputed_at=_clean_string(payload.get("last_updated_at")),
            )
        )


def _coerce_json(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _clean_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_int(value: object) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
