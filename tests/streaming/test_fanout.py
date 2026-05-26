import json

import pytest
from dimoo_run.core.events import AgentEvent
from dimoo_run.streaming.fanout import RedisStreamFanOutBridge, StreamFanOutHub


class FakeRedis:
    def __init__(self) -> None:
        self.streams: dict[str, list[dict[str, str]]] = {}
        self.published: list[tuple[str, str]] = []

    def xadd(self, stream: str, fields: dict[str, str]) -> str:
        self.streams.setdefault(stream, []).append(fields)
        return f"{len(self.streams[stream])}-0"

    def publish(self, channel: str, value: str) -> int:
        self.published.append((channel, value))
        return 1


def test_stream_fanout_delivers_events_to_subscribers() -> None:
    hub = StreamFanOutHub(max_buffer_size=2)
    first = hub.subscribe("run_1", "subscriber_1")
    second = hub.subscribe("run_1", "subscriber_2")

    delivered = hub.publish("run_1", AgentEvent("agent.stream_chunk", {"delta": "hello"}))

    assert delivered == 2
    assert [event.payload for event in first.drain()] == [{"delta": "hello"}]
    assert [event.payload for event in second.drain()] == [{"delta": "hello"}]


def test_stream_fanout_disconnects_slow_subscriber_on_backpressure() -> None:
    hub = StreamFanOutHub(max_buffer_size=1)
    subscriber = hub.subscribe("run_1", "slow")
    hub.publish("run_1", AgentEvent("agent.stream_chunk", {"delta": "first"}))

    delivered = hub.publish("run_1", AgentEvent("agent.stream_chunk", {"delta": "second"}))

    assert delivered == 0
    assert subscriber.disconnected is True
    assert subscriber.disconnect_reason == "stream_backpressure"
    assert hub.subscriber_count("run_1") == 0


@pytest.mark.asyncio
async def test_redis_stream_fanout_writes_replay_stream_and_pubsub() -> None:
    redis = FakeRedis()
    bridge = RedisStreamFanOutBridge(redis)

    stream_id = await bridge.publish(
        "run_1",
        AgentEvent(
            "agent.stream_chunk",
            {"delta": "hello"},
            run_id="run_1",
            sequence=3,
            event_id="run_1:3",
        ),
    )

    assert stream_id == "1-0"
    assert list(redis.streams) == ["dimoorun:stream:run_1"]
    stored = json.loads(redis.streams["dimoorun:stream:run_1"][0]["event"])
    assert stored["event_id"] == "run_1:3"
    assert stored["payload"] == {"delta": "hello"}
    assert redis.published[0][0] == "dimoorun:fanout:run_1"
    assert json.loads(redis.published[0][1]) == stored
