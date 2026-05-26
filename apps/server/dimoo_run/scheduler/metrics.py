from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.domain.models import Task


@dataclass(frozen=True)
class QueueMetrics:
    queue_depth: int
    running_task_count: int
    lease_expired_count: int
    retry_count: int
    dead_letter_count: int
    worker_heartbeat_age_seconds: float | None = None


class SQLAlchemySchedulerMetrics:
    def __init__(self, session: Session) -> None:
        self.session = session

    def snapshot(
        self,
        *,
        queue: str = "default",
        now: datetime | None = None,
        worker_heartbeat_at: datetime | None = None,
    ) -> QueueMetrics:
        current = now or datetime.now(UTC)
        heartbeat_age = None
        if worker_heartbeat_at is not None:
            heartbeat_age = (current - worker_heartbeat_at).total_seconds()
        return QueueMetrics(
            queue_depth=self._count(queue=queue, statuses={"queued"}),
            running_task_count=self._count(queue=queue, statuses={"leased", "running"}),
            lease_expired_count=self._count_expired(queue=queue, now=current),
            retry_count=self._count(queue=queue, statuses={"retrying"}),
            dead_letter_count=self._count(queue=queue, statuses={"dead_letter"}),
            worker_heartbeat_age_seconds=heartbeat_age,
        )

    def _count(self, *, queue: str, statuses: set[str]) -> int:
        statement = select(Task).where(
            Task.queue == queue,
            Task.status.in_(statuses),
            Task.is_deleted.is_(False),
        )
        return len(list(self.session.scalars(statement)))

    def _count_expired(self, *, queue: str, now: datetime) -> int:
        statement = select(Task).where(
            Task.queue == queue,
            Task.status.in_(["leased", "running"]),
            Task.leased_until.is_not(None),
            Task.leased_until < now,
            Task.is_deleted.is_(False),
        )
        return len(list(self.session.scalars(statement)))
