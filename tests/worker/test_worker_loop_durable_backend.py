import json
from datetime import UTC, datetime

import anyio
from dimoo_run.domain.models import Run, Task
from dimoo_run.persistence.database import Base
from dimoo_run.scheduler.redis_backend import RedisCancelSubscriber, RedisTaskBackend
from dimoo_run.scheduler.sqlalchemy_backend import SQLAlchemyTaskBackend
from dimoo_run.worker.loop import WorkerLoop
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class FakeCancelSubscriber:
    async def listen_once(self) -> dict[str, int | str]:
        return {
            "run_id": 1,
            "task_id": 1,
            "worker_id": "worker_1",
            "status": "cancelled",
        }


class FakeCancelHandler:
    def __init__(self) -> None:
        self.cancelled: tuple[str, str | None] | None = None

    async def cancel_run(self, run_id: int, *, task_id: int | None = None) -> str:
        self.cancelled = (run_id, task_id)
        return "adapter_cancelled"


class FakePubSub:
    def __init__(self, redis: "PubSubRedis") -> None:
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


class PubSubRedis:
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
        self.pubsub_messages.append({"data": value})

    def pubsub(self) -> FakePubSub:
        return FakePubSub(self)

    def incr(self, key: str) -> int:
        value = self.counters.get(key, 0) + 1
        self.counters[key] = value
        return value


class FakeExecuteOnce:
    def __init__(self) -> None:
        self.called = False

    async def __call__(self, *, queue: str, lease_seconds: int) -> object:
        self.called = True
        assert queue == "default"
        assert lease_seconds == 30
        return object()


class StopAfterExecuteOnce:
    def __init__(self, loop: WorkerLoop) -> None:
        self.loop = loop
        self.calls = 0

    async def __call__(self, *, queue: str, lease_seconds: int) -> object:
        _ = queue, lease_seconds
        self.calls += 1
        self.loop.stop()
        return object()


def test_worker_loop_uses_executor_callback_before_lease_only_path() -> None:
    execute_once = FakeExecuteOnce()
    loop = WorkerLoop(worker_id="worker_1", execute_once=execute_once)

    heartbeat = loop.run_once()

    assert heartbeat.status == "executed"
    assert execute_once.called is True


def test_worker_loop_run_forever_uses_executor_callback() -> None:
    loop = WorkerLoop(worker_id="worker_1", poll_interval_seconds=0)
    execute_once = StopAfterExecuteOnce(loop)
    loop.execute_once = execute_once

    loop.run_forever()

    assert execute_once.calls == 1
    assert loop.heartbeat.status == "executed"


def test_worker_loop_can_lease_durable_task_and_mark_it_running() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        Run(
            tenant_id=1,
            project_id=1,
            agent_id=1,
            agent_version_id=1,
            input_ref='json:{"message":"hello"}',
        )
    )
    session.flush()
    run_id = session.query(Run.id).scalar()
    assert run_id is not None
    backend = SQLAlchemyTaskBackend(session, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    task_id = anyio.run(
        backend.enqueue,
        {
            "tenant_id": 1,
            "project_id": 1,
            "run_id": run_id,
            "queue": "default",
        },
    )
    loop = WorkerLoop(worker_id="worker_1", task_backend=backend)

    heartbeat = loop.run_once()

    task = backend._task(task_id)
    assert heartbeat.status == "running"
    assert task.status == "running"
    assert task.worker_id == "worker_1"
    assert task.fencing_token == 1


def test_worker_loop_horizontal_scaling_leases_distinct_tasks() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    run_ids: list[int] = []
    for index in range(3):
        run = Run(
            tenant_id=1,
            project_id=1,
            agent_id=1,
            agent_version_id=1,
            input_ref=f'json:{{"message":"hello {index}"}}',
        )
        session.add(run)
        session.flush()
        run_ids.append(run.id)
    backend = SQLAlchemyTaskBackend(session, now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    for run_id in run_ids:
        anyio.run(
            backend.enqueue,
            {
                "tenant_id": 1,
                "project_id": 1,
                "run_id": run_id,
                "queue": "default",
            },
        )
    loops = [
        WorkerLoop(worker_id=f"worker_{index}", task_backend=backend)
        for index in range(3)
    ]

    heartbeats = [loop.run_once() for loop in loops]

    tasks = list(session.query(Task).order_by(Task.worker_id))
    assert [heartbeat.status for heartbeat in heartbeats] == ["running", "running", "running"]
    assert [task.status for task in tasks] == ["running", "running", "running"]
    assert {task.worker_id for task in tasks} == {"worker_0", "worker_1", "worker_2"}
    assert {task.fencing_token for task in tasks} == {1}


def test_worker_loop_consumes_cancel_message_for_worker() -> None:
    handler = FakeCancelHandler()
    loop = WorkerLoop(
        worker_id="worker_1",
        cancel_subscriber=FakeCancelSubscriber(),
        cancel_handler=handler,
    )

    heartbeat = loop.run_once()

    assert heartbeat.status == "cancel_requested"
    assert handler.cancelled == (1, 1)


def test_worker_loop_consumes_redis_cancel_message_from_backend_publish() -> None:
    redis = PubSubRedis()
    backend = RedisTaskBackend(redis)
    task_id = anyio.run(backend.enqueue, {"queue": "default", "run_id": 99})
    leased = anyio.run(backend.lease, "default", "worker_1", 30)

    assert leased is not None
    handler = FakeCancelHandler()
    loop = WorkerLoop(
        worker_id="worker_1",
        cancel_subscriber=RedisCancelSubscriber(redis),
        cancel_handler=handler,
    )

    anyio.run(backend.cancel, task_id)
    heartbeat = loop.run_once()

    assert heartbeat.status == "cancel_requested"
    assert handler.cancelled == (99, task_id)
    assert redis.published == [
        (
            "dimoorun:cancel",
            json.dumps(
                {
                    "run_id": 99,
                    "status": "cancelled",
                    "task_id": task_id,
                    "worker_id": "worker_1",
                },
                sort_keys=True,
            ),
        )
    ]
# mypy: disable-error-code="assignment,comparison-overlap"
