from typing import Any, Protocol


class TaskBackend(Protocol):
    async def enqueue(self, task: dict[str, Any]) -> str: ...

    async def lease(
        self,
        queue: str,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any] | None: ...

    async def heartbeat(
        self,
        task_id: str,
        worker_id: str,
        lease_seconds: int = 30,
    ) -> None: ...

    async def complete(
        self,
        task_id: str,
        worker_id: str,
        fencing_token: int,
    ) -> None: ...

    async def fail(
        self,
        task_id: str,
        worker_id: str,
        fencing_token: int,
        error: dict[str, Any],
    ) -> None: ...

    async def cancel(self, task_id: str) -> None: ...


class RuntimeTaskBackend(TaskBackend, Protocol):
    def mark_running(self, task_id: str, worker_id: str, fencing_token: int) -> None: ...

    def will_retry(self, task_id: str) -> bool: ...
