import json

import pytest
from dimoo_run.scheduler.in_memory import StaleFencingTokenError, TaskLeaseError
from dimoo_run.scheduler.redis_backend import (
    RedisCancelSubscriber,
    RedisTaskBackend,
    RedisUnavailableError,
)


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.zsets: dict[str, dict[str, float]] = {}
        self.lists: dict[str, list[str]] = {}
        self.published: list[tuple[str, str]] = []
        self.pubsub_messages: list[dict[str, str]] = []
        self.counters: dict[str, int] = {}

    def hset(self, key: str, *, mapping: dict[str, str]) -> None:
        self.hashes.setdefault(key, {}).update(mapping)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        self.zsets.setdefault(key, {}).update(mapping)

    def zrange(self, key: str, start: int, end: int) -> list[str]:
        members = [
            member
            for member, _score in sorted(
                self.zsets.get(key, {}).items(),
                key=lambda item: item[1],
            )
        ]
        return members[start:] if end == -1 else members[start : end + 1]

    def zrem(self, key: str, member: str) -> None:
        self.zsets.setdefault(key, {}).pop(member, None)

    def rpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).append(value)

    def keys(self, pattern: str) -> list[str]:
        prefix = pattern.removesuffix("*")
        return [key for key in self.hashes if key.startswith(prefix)]

    def publish(self, channel: str, value: str) -> None:
        self.published.append((channel, value))

    def pubsub(self) -> "FakePubSub":
        return FakePubSub(self)

    def incr(self, key: str) -> int:
        value = self.counters.get(key, 0) + 1
        self.counters[key] = value
        return value


class EvalRedis(FakeRedis):
    def __init__(self) -> None:
        super().__init__()
        self.eval_calls = 0

    def eval(self, script: str, numkeys: int, *args: str) -> list[str] | None:
        _ = script, numkeys
        self.eval_calls += 1
        queue_key, _prefix, worker_id, leased_until, now = args
        for task_id in self.zrange(queue_key, 0, -1):
            key = f"dimoorun:task:{task_id}"
            task = {name: json.loads(value) for name, value in self.hashes[key].items()}
            if task["status"] != "queued":
                continue
            scheduled_at = task.get("scheduled_at")
            if scheduled_at is not None and scheduled_at > now:
                continue
            task["status"] = "leased"
            task["worker_id"] = worker_id
            task["leased_until"] = leased_until
            task["heartbeat_at"] = now
            task["fencing_token"] = int(task.get("fencing_token", 0)) + 1
            self.hset(
                key,
                mapping={name: json.dumps(value) for name, value in task.items()},
            )
            self.zrem(queue_key, task_id)
            encoded = self.hgetall(key)
            pairs: list[str] = []
            for name, value in encoded.items():
                pairs.extend([name, value])
            return pairs
        return None


class FakePubSub:
    def __init__(self, redis: FakeRedis) -> None:
        self.redis = redis
        self.subscribed: list[str] = []

    def subscribe(self, channel: str) -> None:
        self.subscribed.append(channel)

    def get_message(
        self,
        *,
        ignore_subscribe_messages: bool,
        timeout: int,
    ) -> dict[str, str] | None:
        _ = ignore_subscribe_messages, timeout
        if not self.redis.pubsub_messages:
            return None
        return self.redis.pubsub_messages.pop(0)


async def test_redis_backend_reports_missing_client_dependency() -> None:
    backend = RedisTaskBackend(redis_client=None)

    with pytest.raises(RedisUnavailableError):
        await backend.enqueue({"run_id": 1})


async def test_redis_backend_leases_by_priority_and_sets_fencing_token() -> None:
    redis = FakeRedis()
    backend = RedisTaskBackend(redis)
    low_id = await backend.enqueue(
        {"queue": "default", "priority": 0, "run_id": "run_low"}
    )
    high_id = await backend.enqueue(
        {"queue": "default", "priority": 10, "run_id": "run_high"}
    )

    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    assert leased is not None
    assert leased["task_id"] == high_id
    assert leased["fencing_token"] == 1
    assert backend._sync_task(low_id)["status"] == "queued"
    assert backend._sync_task(high_id)["status"] == "leased"


async def test_redis_backend_uses_eval_for_atomic_lease_when_available() -> None:
    redis = EvalRedis()
    backend = RedisTaskBackend(redis)
    task_id = await backend.enqueue({"queue": "default", "run_id": 1})

    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    assert leased is not None
    assert redis.eval_calls == 1
    assert leased["task_id"] == task_id
    assert leased["status"] == "leased"
    assert leased["worker_id"] == "worker_1"


async def test_redis_backend_checks_owner_and_fencing_token() -> None:
    backend = RedisTaskBackend(FakeRedis())
    task_id = await backend.enqueue({"queue": "default", "run_id": 1})
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    assert leased is not None
    with pytest.raises(TaskLeaseError):
        await backend.complete(
            task_id,
            worker_id="worker_2",
            fencing_token=leased["fencing_token"],
        )
    with pytest.raises(StaleFencingTokenError):
        await backend.complete(task_id, worker_id="worker_1", fencing_token=999)


async def test_redis_backend_fail_retries_then_dead_letters() -> None:
    redis = FakeRedis()
    backend = RedisTaskBackend(redis)
    task_id = await backend.enqueue(
        {"queue": "default", "run_id": 1, "max_attempts": 2, "attempt": 1}
    )
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    assert leased is not None
    await backend.fail(
        task_id,
        worker_id="worker_1",
        fencing_token=leased["fencing_token"],
        error={"message": "boom"},
    )

    task = backend._sync_task(task_id)
    assert task["status"] == "dead_letter"
    assert task["dead_letter_reason"] == "boom"
    assert redis.lists["dimoorun:dead_letters"]


async def test_redis_backend_requeues_expired_lease_with_new_token() -> None:
    backend = RedisTaskBackend(FakeRedis())
    task_id = await backend.enqueue({"queue": "default", "run_id": 1})
    first = await backend.lease("default", worker_id="worker_1", lease_seconds=-1)
    second = await backend.lease("default", worker_id="worker_2", lease_seconds=30)

    assert first is not None
    assert second is not None
    assert second["task_id"] == task_id
    assert second["fencing_token"] == 2


async def test_redis_backend_dead_letters_expired_running_task_after_attempts() -> None:
    backend = RedisTaskBackend(FakeRedis())
    task_id = await backend.enqueue({"queue": "default", "run_id": 1, "max_attempts": 1})
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=-1)

    assert leased is not None
    backend.mark_running(task_id, "worker_1", leased["fencing_token"])
    changed = await backend.reap_expired_leases(queue="default")

    task = backend._sync_task(task_id)
    assert changed == 1
    assert task["status"] == "dead_letter"
    assert task["dead_letter_reason"] == "lease_expired"


async def test_redis_backend_reaper_consumes_attempt_before_requeue() -> None:
    backend = RedisTaskBackend(FakeRedis())
    task_id = await backend.enqueue({"queue": "default", "run_id": 1, "max_attempts": 3})
    leased = await backend.lease("default", worker_id="worker_1", lease_seconds=-1)

    assert leased is not None
    backend.mark_running(task_id, "worker_1", leased["fencing_token"])
    changed = await backend.reap_expired_leases(queue="default")

    task = backend._sync_task(task_id)
    assert changed == 1
    assert task["status"] == "queued"
    assert task["attempt"] == 1


async def test_redis_backend_cancel_publishes_cross_instance_message() -> None:
    redis = FakeRedis()
    backend = RedisTaskBackend(redis)
    task_id = await backend.enqueue({"queue": "default", "run_id": 1})
    await backend.lease("default", worker_id="worker_1", lease_seconds=30)

    await backend.cancel(task_id)

    task = backend._sync_task(task_id)
    assert task["status"] == "cancelled"
    assert redis.published[0][0] == "dimoorun:cancel"
    assert json.loads(redis.published[0][1]) == {
        "run_id": 1,
        "status": "cancelled",
        "task_id": task_id,
        "worker_id": "worker_1",
    }


async def test_redis_cancel_subscriber_reads_cancel_message() -> None:
    redis = FakeRedis()
    redis.pubsub_messages.append(
        {
            "data": json.dumps(
                {
                    "run_id": 1,
                    "status": "cancelled",
                    "task_id": 1,
                    "worker_id": "worker_1",
                }
            )
        }
    )

    message = await RedisCancelSubscriber(redis).listen_once()

    assert message == {
        "run_id": 1,
        "status": "cancelled",
        "task_id": 1,
        "worker_id": "worker_1",
    }
