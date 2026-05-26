from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class WorkerHeartbeat:
    worker_id: str
    status: str
    heartbeat_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class WorkerLoop:
    def __init__(
        self,
        *,
        worker_id: str | None = None,
        poll_interval_seconds: float = 1.0,
        task_backend: Any | None = None,
        queue: str = "default",
        lease_seconds: int = 30,
        cancel_subscriber: Any | None = None,
    ) -> None:
        self.worker_id = worker_id or f"worker_{uuid4().hex[:8]}"
        self.poll_interval_seconds = poll_interval_seconds
        self.task_backend = task_backend
        self.queue = queue
        self.lease_seconds = lease_seconds
        self.cancel_subscriber = cancel_subscriber
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="starting")
        self._stopped = False

    def run_once(self) -> WorkerHeartbeat:
        if self.cancel_subscriber is not None:
            import anyio

            message = anyio.run(self.cancel_subscriber.listen_once)
            if message is not None and message.get("worker_id") in {None, self.worker_id}:
                self.heartbeat = WorkerHeartbeat(
                    worker_id=self.worker_id,
                    status="cancel_requested",
                )
                return self.heartbeat
        if self.task_backend is not None:
            import anyio

            leased = anyio.run(
                self.task_backend.lease,
                self.queue,
                self.worker_id,
                self.lease_seconds,
            )
            if leased is not None:
                self.task_backend.mark_running(
                    leased["task_id"],
                    self.worker_id,
                    leased["fencing_token"],
                )
                self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="running")
                return self.heartbeat
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="idle")
        return self.heartbeat

    def run_forever(self) -> None:
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="running")
        while not self._stopped:
            self.run_once()
            time.sleep(self.poll_interval_seconds)

    def stop(self) -> None:
        self._stopped = True
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="stopped")
