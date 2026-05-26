from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass
class WorkerHeartbeat:
    worker_id: str
    status: str
    heartbeat_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class WorkerLoop:
    def __init__(self, *, worker_id: str | None = None, poll_interval_seconds: float = 1.0) -> None:
        self.worker_id = worker_id or f"worker_{uuid4().hex[:8]}"
        self.poll_interval_seconds = poll_interval_seconds
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="starting")
        self._stopped = False

    def run_once(self) -> WorkerHeartbeat:
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
