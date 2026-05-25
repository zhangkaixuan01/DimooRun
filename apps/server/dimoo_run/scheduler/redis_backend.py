from typing import Any, NoReturn


class RedisUnavailableError(RuntimeError):
    pass


class RedisTaskBackend:
    def __init__(self, redis_client: Any | None) -> None:
        self.redis_client = redis_client

    async def enqueue(self, task: dict[str, Any]) -> str:
        _ = task
        self._require_client()
        self._not_implemented()

    async def lease(
        self,
        queue: str,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        _ = queue, worker_id, lease_seconds
        self._require_client()
        self._not_implemented()

    async def heartbeat(
        self,
        task_id: str,
        worker_id: str,
        lease_seconds: int = 30,
    ) -> None:
        _ = task_id, worker_id, lease_seconds
        self._require_client()
        self._not_implemented()

    async def complete(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        _ = task_id, worker_id, fencing_token
        self._require_client()
        self._not_implemented()

    async def fail(
        self,
        task_id: str,
        worker_id: str,
        fencing_token: int,
        error: dict[str, Any],
    ) -> None:
        _ = task_id, worker_id, fencing_token, error
        self._require_client()
        self._not_implemented()

    async def cancel(self, task_id: str) -> None:
        _ = task_id
        self._require_client()
        self._not_implemented()

    def _require_client(self) -> None:
        if self.redis_client is None:
            raise RedisUnavailableError("Redis client is not configured.")

    def _not_implemented(self) -> NoReturn:
        raise NotImplementedError(
            "RedisTaskBackend command mapping is implemented in production phase."
        )
