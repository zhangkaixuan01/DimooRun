import pytest
from dimoo_run.scheduler.redis_backend import RedisTaskBackend, RedisUnavailableError


async def test_redis_backend_reports_missing_client_dependency() -> None:
    backend = RedisTaskBackend(redis_client=None)

    with pytest.raises(RedisUnavailableError):
        await backend.enqueue({"run_id": "run_1"})
