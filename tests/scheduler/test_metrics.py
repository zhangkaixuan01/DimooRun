from datetime import UTC, datetime, timedelta

from dimoo_run.domain.models import Task
from dimoo_run.persistence.database import Base
from dimoo_run.scheduler.metrics import SQLAlchemySchedulerMetrics
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_sqlalchemy_scheduler_metrics_snapshot_counts_runtime_queue() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    session.add_all(
        [
            _task("task_queued", "queued"),
            _task("task_running", "running"),
            _task("task_leased_expired", "leased", leased_until=now - timedelta(seconds=1)),
            _task("task_retrying", "retrying"),
            _task("task_dead_letter", "dead_letter"),
        ]
    )
    session.flush()

    metrics = SQLAlchemySchedulerMetrics(session).snapshot(
        now=now,
        worker_heartbeat_at=now - timedelta(seconds=15),
    )

    assert metrics.queue_depth == 1
    assert metrics.running_task_count == 2
    assert metrics.lease_expired_count == 1
    assert metrics.retry_count == 1
    assert metrics.dead_letter_count == 1
    assert metrics.worker_heartbeat_age_seconds == 15


def _task(
    task_id: int,
    status: str,
    *,
    leased_until: datetime | None = None,
) -> Task:
    return Task(
        id=task_id,
        run_id=f"run_{task_id}",
        tenant_id=1,
        project_id=1,
        status=status,
        queue="default",
        leased_until=leased_until,
    )
