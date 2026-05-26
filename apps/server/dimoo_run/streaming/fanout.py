import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from dimoo_run.core.events import AgentEvent


class StreamBackpressureError(RuntimeError):
    error_code = "stream_backpressure"


@dataclass
class StreamSubscriber:
    subscriber_id: str
    max_buffer_size: int
    buffer: deque[AgentEvent] = field(default_factory=deque)
    disconnected: bool = False
    disconnect_reason: str | None = None

    def push(self, event: AgentEvent) -> None:
        if self.disconnected:
            return
        if len(self.buffer) >= self.max_buffer_size:
            self.disconnected = True
            self.disconnect_reason = StreamBackpressureError.error_code
            raise StreamBackpressureError(self.subscriber_id)
        self.buffer.append(event)

    def drain(self) -> list[AgentEvent]:
        events = list(self.buffer)
        self.buffer.clear()
        return events


class StreamFanOutHub:
    def __init__(self, *, max_buffer_size: int = 100) -> None:
        self.max_buffer_size = max_buffer_size
        self._subscribers: dict[str, dict[str, StreamSubscriber]] = {}

    def subscribe(self, run_id: str, subscriber_id: str) -> StreamSubscriber:
        subscriber = StreamSubscriber(
            subscriber_id=subscriber_id,
            max_buffer_size=self.max_buffer_size,
        )
        self._subscribers.setdefault(run_id, {})[subscriber_id] = subscriber
        return subscriber

    def unsubscribe(self, run_id: str, subscriber_id: str) -> None:
        self._subscribers.get(run_id, {}).pop(subscriber_id, None)

    def publish(self, run_id: str, event: AgentEvent) -> int:
        delivered = 0
        subscribers = list(self._subscribers.get(run_id, {}).values())
        for subscriber in subscribers:
            try:
                subscriber.push(event)
                delivered += 1
            except StreamBackpressureError:
                self.unsubscribe(run_id, subscriber.subscriber_id)
        return delivered

    def subscriber_count(self, run_id: str) -> int:
        return len(self._subscribers.get(run_id, {}))


class RedisStreamFanOutBridge:
    def __init__(
        self,
        redis_client: Any,
        *,
        stream_prefix: str = "dimoorun:stream",
        channel_prefix: str = "dimoorun:fanout",
    ) -> None:
        self.redis_client = redis_client
        self.stream_prefix = stream_prefix
        self.channel_prefix = channel_prefix

    async def publish(self, run_id: str, event: AgentEvent) -> str | None:
        payload = {
            "run_id": run_id,
            "attempt_id": event.attempt_id,
            "sequence": event.sequence,
            "event_id": event.event_id,
            "type": event.type,
            "payload": event.payload,
            "visibility_level": event.visibility_level,
        }
        stream_id = await _maybe_await(
            self.redis_client.xadd(
                f"{self.stream_prefix}:{run_id}",
                {"event": json.dumps(payload, sort_keys=True, separators=(",", ":"))},
            )
        )
        publish = getattr(self.redis_client, "publish", None)
        if publish is not None:
            await _maybe_await(
                publish(
                    f"{self.channel_prefix}:{run_id}",
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                )
            )
        return str(stream_id) if stream_id is not None else None


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
