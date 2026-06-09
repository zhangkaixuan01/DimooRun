import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, cast

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
        self._subscribers: dict[int, dict[str, StreamSubscriber]] = {}

    def subscribe(self, run_id: int, subscriber_id: str) -> StreamSubscriber:
        subscriber = StreamSubscriber(
            subscriber_id=subscriber_id,
            max_buffer_size=self.max_buffer_size,
        )
        self._subscribers.setdefault(run_id, {})[subscriber_id] = subscriber
        return subscriber

    def unsubscribe(self, run_id: int, subscriber_id: str) -> None:
        self._subscribers.get(run_id, {}).pop(subscriber_id, None)

    def publish(self, run_id: int, event: AgentEvent) -> int:
        delivered = 0
        subscribers = list(self._subscribers.get(run_id, {}).values())
        for subscriber in subscribers:
            try:
                subscriber.push(event)
                delivered += 1
            except StreamBackpressureError:
                self.unsubscribe(run_id, subscriber.subscriber_id)
        return delivered

    def subscriber_count(self, run_id: int) -> int:
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
        self._pubsubs: dict[int, Any] = {}

    async def publish(self, run_id: int, event: AgentEvent) -> str | None:
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

    async def replay(self, run_id: int, *, last_event_id: str | None = None) -> list[AgentEvent]:
        start = "-"
        if last_event_id is not None:
            start = f"({last_event_id}"
        entries = await _maybe_await(
            self.redis_client.xrange(f"{self.stream_prefix}:{run_id}", min=start, max="+")
        )
        return [_event_from_payload(_event_payload(fields)) for _stream_id, fields in entries]

    async def relay_once(self, run_id: int, hub: StreamFanOutHub) -> int:
        pubsub = self._pubsubs.get(run_id)
        if pubsub is None:
            pubsub = self.redis_client.pubsub()
            await _maybe_await(pubsub.subscribe(f"{self.channel_prefix}:{run_id}"))
            self._pubsubs[run_id] = pubsub
        message = cast(
            dict[str, Any] | None,
            await _maybe_await(
            pubsub.get_message(ignore_subscribe_messages=True, timeout=0)
            ),
        )
        if not message:
            return 0
        data = message.get("data")
        if isinstance(data, bytes):
            data = data.decode()
        payload = json.loads(str(data))
        return hub.publish(run_id, _event_from_payload(payload))


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _event_payload(fields: dict[str, Any]) -> dict[str, Any]:
    value = fields.get("event")
    if isinstance(value, bytes):
        value = value.decode()
    return cast(dict[str, Any], json.loads(str(value)))


def _event_from_payload(payload: dict[str, Any]) -> AgentEvent:
    run_id = payload.get("run_id")
    attempt_id = payload.get("attempt_id")
    sequence = payload.get("sequence")
    return AgentEvent(
        type=payload["type"],
        payload=payload.get("payload") or {},
        run_id=int(run_id) if run_id is not None else None,
        attempt_id=int(attempt_id) if attempt_id is not None else None,
        sequence=int(sequence) if sequence is not None else None,
        event_id=payload.get("event_id"),
        visibility_level=payload.get("visibility_level", "internal"),
    )
