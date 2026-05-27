import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from dimoo_run.runtime.state_machine import assert_task_transition
from dimoo_run.scheduler.in_memory import StaleFencingTokenError, TaskLeaseError


class RedisUnavailableError(RuntimeError):
    pass


class RedisTaskBackend:
    def __init__(self, redis_client: Any | None, *, prefix: str = "dimoorun") -> None:
        self.redis_client = redis_client
        self.prefix = prefix

    async def enqueue(self, task: dict[str, Any]) -> str:
        self._require_client()
        task_id = task.get("task_id") or f"task_{uuid4().hex[:12]}"
        now = _now()
        record = {
            **task,
            "task_id": task_id,
            "queue": task.get("queue", "default"),
            "priority": task.get("priority", 0),
            "status": "queued",
            "attempt": task.get("attempt", 0),
            "max_attempts": task.get("max_attempts", 3),
            "fencing_token": 0,
            "created_at": task.get("created_at") or now.isoformat(),
        }
        await self._hset(self._task_key(task_id), mapping=_encode_mapping(record))
        await self._zadd(self._queue_key(record["queue"]), {task_id: _queue_score(record)})
        return task_id

    async def lease(
        self,
        queue: str,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        self._require_client()
        await self.reap_expired_leases(queue=queue)
        now = _now()
        atomic_lease = await self._lease_with_eval(
            queue=queue,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            now=now,
        )
        if atomic_lease is not None:
            return atomic_lease
        for task_id in await self._zrange(self._queue_key(queue), 0, -1):
            task = await self._task(str(task_id))
            if task.get("status") != "queued":
                continue
            scheduled_at = _parse_dt(task.get("scheduled_at"))
            if scheduled_at is not None and scheduled_at > now:
                continue
            assert_task_transition(task["status"], "leased")
            task["status"] = "leased"
            task["worker_id"] = worker_id
            task["leased_until"] = (now + timedelta(seconds=lease_seconds)).isoformat()
            task["heartbeat_at"] = now.isoformat()
            task["fencing_token"] = int(task.get("fencing_token", 0)) + 1
            await self._hset(self._task_key(task["task_id"]), mapping=_encode_mapping(task))
            await self._zrem(self._queue_key(queue), task["task_id"])
            return task
        return None

    async def heartbeat(
        self,
        task_id: str,
        worker_id: str,
        lease_seconds: int = 30,
    ) -> None:
        task = await self._owned_task(task_id, worker_id)
        now = _now()
        task["heartbeat_at"] = now.isoformat()
        task["leased_until"] = (now + timedelta(seconds=lease_seconds)).isoformat()
        await self._hset(self._task_key(task_id), mapping=_encode_mapping(task))

    async def complete(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        task = await self._task(task_id)
        self._assert_fencing_token(task, fencing_token)
        self._assert_owner(task, worker_id)
        if task["status"] == "leased":
            assert_task_transition(task["status"], "running")
            task["status"] = "running"
        assert_task_transition(task["status"], "succeeded")
        task["status"] = "succeeded"
        task["finished_at"] = _now().isoformat()
        task["leased_until"] = None
        await self._hset(self._task_key(task_id), mapping=_encode_mapping(task))

    async def fail(
        self,
        task_id: str,
        worker_id: str,
        fencing_token: int,
        error: dict[str, Any],
    ) -> None:
        task = await self._task(task_id)
        self._assert_fencing_token(task, fencing_token)
        self._assert_owner(task, worker_id)
        if task["status"] == "leased":
            assert_task_transition(task["status"], "running")
            task["status"] = "running"
        assert_task_transition(task["status"], "failed")
        task["status"] = "failed"
        task["error"] = error
        if int(task.get("attempt", 0)) + 1 >= int(task.get("max_attempts", 3)):
            assert_task_transition(task["status"], "dead_letter")
            task["status"] = "dead_letter"
            task["dead_letter_reason"] = _error_message(error)
            task["finished_at"] = _now().isoformat()
            task["leased_until"] = None
            await self._hset(self._task_key(task_id), mapping=_encode_mapping(task))
            await self._rpush(
                self._dead_letter_key(),
                json.dumps({"task_id": task_id, "error": error}),
            )
            return
        assert_task_transition(task["status"], "retrying")
        task["status"] = "retrying"
        task["attempt"] = int(task.get("attempt", 0)) + 1
        task["worker_id"] = None
        task["leased_until"] = None
        assert_task_transition(task["status"], "queued")
        task["status"] = "queued"
        await self._hset(self._task_key(task_id), mapping=_encode_mapping(task))
        await self._zadd(self._queue_key(task["queue"]), {task_id: _queue_score(task)})

    async def cancel(self, task_id: str) -> None:
        task = await self._task(task_id)
        if task["status"] == "leased":
            assert_task_transition(task["status"], "running")
            task["status"] = "running"
        assert_task_transition(task["status"], "cancelled")
        task["status"] = "cancelled"
        task["finished_at"] = _now().isoformat()
        await self._hset(self._task_key(task_id), mapping=_encode_mapping(task))
        await self._zrem(self._queue_key(task["queue"]), task_id)
        await self._publish(
            self._cancel_channel(),
            json.dumps(
                {
                    "task_id": task_id,
                    "run_id": task.get("run_id"),
                    "worker_id": task.get("worker_id"),
                    "status": "cancelled",
                },
                sort_keys=True,
            ),
        )

    def mark_running(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        task = self._sync_task(task_id)
        self._assert_fencing_token(task, fencing_token)
        self._assert_owner(task, worker_id)
        assert_task_transition(task["status"], "running")
        task["status"] = "running"
        task["started_at"] = task.get("started_at") or _now().isoformat()
        self._sync_hset(self._task_key(task_id), mapping=_encode_mapping(task))

    def assert_can_complete(self, task_id: str, worker_id: str, fencing_token: int) -> None:
        task = self._sync_task(task_id)
        self._assert_fencing_token(task, fencing_token)
        self._assert_owner(task, worker_id)

    def will_retry(self, task_id: str) -> bool:
        task = self._sync_task(task_id)
        return int(task.get("attempt", 0)) + 1 < int(task.get("max_attempts", 3))

    async def reap_expired_leases(self, *, queue: str | None = None) -> int:
        now = _now()
        queues = [queue] if queue is not None else await self._known_queues()
        requeued = 0
        for queue_name in queues:
            for task_id in await self._scan_task_ids():
                task = await self._task(str(task_id))
                if queue_name is not None and task.get("queue") != queue_name:
                    continue
                leased_until = _parse_dt(task.get("leased_until"))
                if task.get("status") not in {"leased", "running"} or leased_until is None:
                    continue
                if leased_until >= now:
                    continue
                if task["status"] == "running":
                    if int(task.get("attempt", 0)) + 1 >= int(task.get("max_attempts", 3)):
                        assert_task_transition(task["status"], "dead_letter")
                        task["status"] = "dead_letter"
                        task["dead_letter_reason"] = "lease_expired"
                        task["worker_id"] = None
                        task["leased_until"] = None
                        await self._hset(
                            self._task_key(task["task_id"]),
                            mapping=_encode_mapping(task),
                        )
                        requeued += 1
                        continue
                    assert_task_transition(task["status"], "retrying")
                    task["status"] = "retrying"
                    task["attempt"] = int(task.get("attempt", 0)) + 1
                assert_task_transition(task["status"], "queued")
                task["status"] = "queued"
                task["worker_id"] = None
                task["leased_until"] = None
                await self._hset(self._task_key(task["task_id"]), mapping=_encode_mapping(task))
                await self._zadd(
                    self._queue_key(task["queue"]),
                    {task["task_id"]: _queue_score(task)},
                )
                requeued += 1
        return requeued

    async def _owned_task(self, task_id: str, worker_id: str) -> dict[str, Any]:
        task = await self._task(task_id)
        self._assert_owner(task, worker_id)
        return task

    async def _task(self, task_id: str) -> dict[str, Any]:
        encoded = await self._hgetall(self._task_key(task_id))
        if not encoded:
            raise KeyError(task_id)
        return _decode_mapping(encoded)

    def _sync_task(self, task_id: str) -> dict[str, Any]:
        encoded = self._sync_hgetall(self._task_key(task_id))
        if not encoded:
            raise KeyError(task_id)
        return _decode_mapping(encoded)

    def _assert_fencing_token(self, task: dict[str, Any], fencing_token: int) -> None:
        if int(task.get("fencing_token", 0)) != fencing_token:
            raise StaleFencingTokenError(str(task["task_id"]))

    def _assert_owner(self, task: dict[str, Any], worker_id: str) -> None:
        if task.get("worker_id") != worker_id:
            raise TaskLeaseError(f"Task {task['task_id']} is not leased by {worker_id}.")

    def _require_client(self) -> None:
        if self.redis_client is None:
            raise RedisUnavailableError("Redis client is not configured.")

    def _client(self) -> Any:
        self._require_client()
        return self.redis_client

    def _task_key(self, task_id: str) -> str:
        return f"{self.prefix}:task:{task_id}"

    def _queue_key(self, queue: str) -> str:
        return f"{self.prefix}:queue:{queue}"

    def _dead_letter_key(self) -> str:
        return f"{self.prefix}:dead_letters"

    def _cancel_channel(self) -> str:
        return f"{self.prefix}:cancel"

    async def _known_queues(self) -> list[str]:
        return ["default"]

    async def _scan_task_ids(self) -> list[str]:
        keys = await self._keys(f"{self.prefix}:task:*")
        return [str(key).rsplit(":", 1)[-1] for key in keys]

    async def _hset(self, key: str, *, mapping: dict[str, str]) -> Any:
        return await _maybe_await(self._client().hset(key, mapping=mapping))

    def _sync_hset(self, key: str, *, mapping: dict[str, str]) -> Any:
        return self._client().hset(key, mapping=mapping)

    async def _hgetall(self, key: str) -> dict[str, str]:
        return cast(dict[str, str], await _maybe_await(self._client().hgetall(key)))

    def _sync_hgetall(self, key: str) -> dict[str, str]:
        return cast(dict[str, str], self._client().hgetall(key))

    async def _zadd(self, key: str, mapping: dict[str, float]) -> Any:
        return await _maybe_await(self._client().zadd(key, mapping))

    async def _zrange(self, key: str, start: int, end: int) -> list[str]:
        return cast(list[str], await _maybe_await(self._client().zrange(key, start, end)))

    async def _zrem(self, key: str, member: str) -> Any:
        return await _maybe_await(self._client().zrem(key, member))

    async def _rpush(self, key: str, value: str) -> Any:
        return await _maybe_await(self._client().rpush(key, value))

    async def _publish(self, channel: str, value: str) -> Any:
        publish = getattr(self._client(), "publish", None)
        if publish is None:
            return None
        return await _maybe_await(publish(channel, value))

    async def _keys(self, pattern: str) -> list[str]:
        return cast(list[str], await _maybe_await(self._client().keys(pattern)))

    async def _lease_with_eval(
        self,
        *,
        queue: str,
        worker_id: str,
        lease_seconds: int,
        now: datetime,
    ) -> dict[str, Any] | None:
        eval_fn = getattr(self._client(), "eval", None)
        if eval_fn is None:
            return None
        leased_until = (now + timedelta(seconds=lease_seconds)).isoformat()
        response = await _maybe_await(
            eval_fn(
                _LEASE_SCRIPT,
                1,
                self._queue_key(queue),
                self.prefix,
                worker_id,
                leased_until,
                now.isoformat(),
            )
        )
        if not response:
            return None
        return _decode_hgetall_response(response)


class RedisCancelSubscriber:
    def __init__(self, redis_client: Any, *, prefix: str = "dimoorun") -> None:
        self.redis_client = redis_client
        self.prefix = prefix
        self._pubsub: Any | None = None

    async def listen_once(self) -> dict[str, Any] | None:
        if self._pubsub is None:
            self._pubsub = self.redis_client.pubsub()
            await _maybe_await(self._pubsub.subscribe(f"{self.prefix}:cancel"))
        message = await _maybe_await(
            self._pubsub.get_message(ignore_subscribe_messages=True, timeout=0)
        )
        if not message:
            return None
        data = message.get("data")
        if isinstance(data, bytes):
            data = data.decode()
        return cast(dict[str, Any], json.loads(str(data)))


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _encode_mapping(task: dict[str, Any]) -> dict[str, str]:
    return {key: json.dumps(value, default=str) for key, value in task.items()}


def _decode_mapping(task: dict[str, Any]) -> dict[str, Any]:
    return {_decode_key(key): json.loads(_decode_value(value)) for key, value in task.items()}


def _decode_key(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def _decode_value(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def _queue_score(task: dict[str, Any]) -> float:
    priority = int(task.get("priority", 0))
    created_at = _parse_dt(task.get("created_at")) or _now()
    return -priority * 1_000_000_000_000 + created_at.timestamp()


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _now() -> datetime:
    return datetime.now(UTC)


def _error_message(error: dict[str, Any]) -> str:
    message = error.get("message")
    return str(message if message is not None else error)


def _decode_hgetall_response(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return _decode_mapping(response)
    pairs = list(response)
    return _decode_mapping(dict(zip(pairs[0::2], pairs[1::2], strict=False)))


_LEASE_SCRIPT = """
local queue_key = KEYS[1]
local prefix = ARGV[1]
local worker_id = ARGV[2]
local leased_until = ARGV[3]
local now = ARGV[4]
local task_ids = redis.call("ZRANGE", queue_key, 0, -1)
for _, task_id in ipairs(task_ids) do
  local task_key = prefix .. ":task:" .. task_id
  local values = redis.call("HGETALL", task_key)
  local task = {}
  for index = 1, #values, 2 do
    task[values[index]] = cjson.decode(values[index + 1])
  end
  if task["status"] == "queued" then
    local scheduled_at = task["scheduled_at"]
    if scheduled_at == nil or scheduled_at <= now then
      local token = tonumber(task["fencing_token"] or 0) + 1
      redis.call(
        "HSET",
        task_key,
        "status", cjson.encode("leased"),
        "worker_id", cjson.encode(worker_id),
        "leased_until", cjson.encode(leased_until),
        "heartbeat_at", cjson.encode(now),
        "fencing_token", cjson.encode(token)
      )
      redis.call("ZREM", queue_key, task_id)
      return redis.call("HGETALL", task_key)
    end
  end
end
return nil
"""
