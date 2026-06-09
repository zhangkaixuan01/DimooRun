import json

import pytest
from dimoo_run.core.events import AgentEvent
from dimoo_run.streaming.fanout import RedisStreamFanOutBridge, StreamFanOutHub


class FakeRedis:
    def __init__(self) -> None:
        self.streams: dict[str, list[dict[str, str]]] = {}
        self.published: list[tuple[str, str]] = []
        self.pubsub_messages: list[dict[str, str]] = []

    def xadd(self, stream: str, fields: dict[str, str]) -> str:
        self.streams.setdefault(stream, []).append(fields)
        return f"{len(self.streams[stream])}-0"

    def xrange(self, stream: str, *, min: str, max: str) -> list[tuple[str, dict[str, str]]]:
        _ = max
        entries = [
            (f"{index + 1}-0", fields)
            for index, fields in enumerate(self.streams.get(stream, []))
        ]
        if min.startswith("("):
            last = int(min[1:].rsplit(":", 1)[-1])
            return entries[last:]
        return entries

    def publish(self, channel: str, value: str) -> int:
        self.published.append((channel, value))
        return 1

    def pubsub(self) -> "FakePubSub":
        return FakePubSub(self)


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


def test_stream_fanout_delivers_events_to_subscribers() -> None:
    hub = StreamFanOutHub(max_buffer_size=2)
    first = hub.subscribe(1, "subscriber_1")
    second = hub.subscribe(1, "subscriber_2")

    delivered = hub.publish(1, AgentEvent("agent.stream_chunk", {"delta": "hello"}))

    assert delivered == 2
    assert [event.payload for event in first.drain()] == [{"delta": "hello"}]
    assert [event.payload for event in second.drain()] == [{"delta": "hello"}]


def test_stream_fanout_disconnects_slow_subscriber_on_backpressure() -> None:
    hub = StreamFanOutHub(max_buffer_size=1)
    subscriber = hub.subscribe(1, "slow")
    hub.publish(1, AgentEvent("agent.stream_chunk", {"delta": "first"}))

    delivered = hub.publish(1, AgentEvent("agent.stream_chunk", {"delta": "second"}))

    assert delivered == 0
    assert subscriber.disconnected is True
    assert subscriber.disconnect_reason == "stream_backpressure"
    assert hub.subscriber_count(1) == 0


@pytest.mark.asyncio
async def test_redis_stream_fanout_writes_replay_stream_and_pubsub() -> None:
    redis = FakeRedis()
    bridge = RedisStreamFanOutBridge(redis)

    stream_id = await bridge.publish(
        1,
        AgentEvent(
            "agent.stream_chunk",
            {"delta": "hello"},
            run_id=1,
            sequence=3,
            event_id="1:3",
        ),
    )

    assert stream_id == "1-0"
    assert list(redis.streams) == ["dimoorun:stream:1"]
    stored = json.loads(redis.streams["dimoorun:stream:1"][0]["event"])
    assert stored["event_id"] == "1:3"
    assert stored["payload"] == {"delta": "hello"}
    assert redis.published[0][0] == "dimoorun:fanout:1"
    assert json.loads(redis.published[0][1]) == stored


@pytest.mark.asyncio
async def test_redis_stream_fanout_replays_after_last_event_id() -> None:
    redis = FakeRedis()
    bridge = RedisStreamFanOutBridge(redis)
    await bridge.publish(
        1,
        AgentEvent("agent.stream_chunk", {"delta": "first"}, run_id=1, sequence=1),
    )
    await bridge.publish(
        1,
        AgentEvent("agent.stream_chunk", {"delta": "second"}, run_id=1, sequence=2),
    )

    events = await bridge.replay(1, last_event_id="1:1")

    assert [event.event_id for event in events] == ["1:2"]
    assert events[0].payload == {"delta": "second"}


@pytest.mark.asyncio
async def test_redis_stream_fanout_relays_pubsub_to_local_hub() -> None:
    redis = FakeRedis()
    hub = StreamFanOutHub()
    subscriber = hub.subscribe(1, "subscriber_1")
    payload = {
        "run_id": 1,
        "attempt_id": None,
        "sequence": 1,
        "event_id": "1:1",
        "type": "agent.stream_chunk",
        "payload": {"delta": "hello"},
        "visibility_level": "internal",
    }
    redis.pubsub_messages.append({"data": json.dumps(payload)})

    delivered = await RedisStreamFanOutBridge(redis).relay_once(1, hub)

    assert delivered == 1
    assert [event.payload for event in subscriber.drain()] == [{"delta": "hello"}]
