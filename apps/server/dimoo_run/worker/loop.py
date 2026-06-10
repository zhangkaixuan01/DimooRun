from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from dimoo_run.runtime.capacity import default_worker_registry


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
        cancel_handler: Any | None = None,
        execute_once: Any | None = None,
        tenant_id: int = 1,
        project_id: int = 1,
        environment: str = "production",
        version: str = "dev",
        capacity: int = 1,
    ) -> None:
        self.worker_id = worker_id or f"worker_{uuid4().hex[:8]}"
        self.poll_interval_seconds = poll_interval_seconds
        self.task_backend = task_backend
        self.queue = queue
        self.lease_seconds = lease_seconds
        self.cancel_subscriber = cancel_subscriber
        self.cancel_handler = cancel_handler
        self.execute_once = execute_once
        self.tenant_id = tenant_id
        self.project_id = project_id
        self.environment = environment
        self.version = version
        self.capacity = capacity
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="starting")
        self._stopped = False
        self._publish_heartbeat("starting")

    def run_once(self) -> WorkerHeartbeat:
        if self.cancel_subscriber is not None:
            import anyio

            message = anyio.run(self.cancel_subscriber.listen_once)
            if message is not None and message.get("worker_id") in {None, self.worker_id}:
                self._handle_cancel_message(message)
                self.heartbeat = WorkerHeartbeat(
                    worker_id=self.worker_id,
                    status="cancel_requested",
                )
                self._publish_heartbeat("cancel_requested")
                return self.heartbeat
        if self.execute_once is not None:
            import anyio
            execute_once = self.execute_once

            async def invoke_execute_once() -> Any:
                return await execute_once(
                    queue=self.queue,
                    lease_seconds=self.lease_seconds,
                )

            result = anyio.run(invoke_execute_once)
            if result is not None:
                self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="executed")
                self._publish_heartbeat("executed")
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
                self._publish_heartbeat("running")
                return self.heartbeat
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="idle")
        self._publish_heartbeat("idle")
        return self.heartbeat

    def run_forever(self) -> None:
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="running")
        self._publish_heartbeat("running")
        while not self._stopped:
            self.run_once()
            time.sleep(self.poll_interval_seconds)

    def stop(self) -> None:
        self._stopped = True
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id, status="stopped")
        self._publish_heartbeat("stopped")

    def _handle_cancel_message(self, message: dict[str, Any]) -> None:
        if self.cancel_handler is None:
            return
        run_id = message.get("run_id")
        if run_id is None:
            return
        import anyio

        handler = self.cancel_handler
        if hasattr(handler, "cancel_run"):
            async def invoke_cancel() -> None:
                await handler.cancel_run(run_id, task_id=message.get("task_id"))

            anyio.run(invoke_cancel)
            return
        assert callable(handler)
        anyio.run(handler, message)

    def _publish_heartbeat(self, status: str) -> None:
        default_worker_registry().heartbeat(
            worker_id=self.worker_id,
            tenant_id=self.tenant_id,
            project_id=self.project_id,
            environment=self.environment,
            status=status,
            queues=[self.queue],
            version=self.version,
            capacity=self.capacity,
        )
