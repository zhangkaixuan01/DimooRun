from dimoo_run.core.events import AgentEvent
from dimoo_run.streaming.replay_buffer import ReplayBuffer, ReplayExpiredError


def test_replay_buffer_assigns_sequence_and_event_id_per_run() -> None:
    buffer = ReplayBuffer(max_events_per_run=10)

    first = buffer.append(1, 1, AgentEvent("run.started", {}))
    second = buffer.append(1, 1, AgentEvent("agent.stream_chunk", {"delta": "a"}))

    assert first.sequence == 1
    assert first.event_id == "1:1"
    assert first.attempt_id == 1
    assert second.sequence == 2
    assert second.event_id == "1:2"


def test_replay_buffer_replays_after_last_event_id() -> None:
    buffer = ReplayBuffer(max_events_per_run=10)
    buffer.append(1, None, AgentEvent("run.started", {}))
    buffer.append(1, None, AgentEvent("agent.stream_chunk", {"delta": "a"}))
    buffer.append(1, None, AgentEvent("stream.completed", {}))

    events = buffer.replay(1, last_event_id="1:1")

    assert [event.event_id for event in events] == ["1:2", "1:3"]


def test_replay_buffer_reports_expired_last_event_id() -> None:
    buffer = ReplayBuffer(max_events_per_run=2)
    buffer.append(1, None, AgentEvent("run.started", {}))
    buffer.append(1, None, AgentEvent("agent.stream_chunk", {"delta": "a"}))
    buffer.append(1, None, AgentEvent("stream.completed", {}))

    try:
        buffer.replay(1, last_event_id="1:1")
    except ReplayExpiredError as exc:
        assert exc.event.type == "stream.replay_expired"
        assert exc.event.visibility_level == "transport"
        assert exc.event.event_id == "1:replay-expired:1"
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected ReplayExpiredError")

    assert [event.event_id for event in buffer.replay(1)] == ["1:2", "1:3"]


def test_replay_buffer_rejects_payloads_that_exceed_inline_limit() -> None:
    buffer = ReplayBuffer(max_payload_bytes=8)

    event = buffer.append(1, None, AgentEvent("agent.stream_chunk", {"delta": "too-long"}))

    assert event.payload == {
        "payload_ref": "artifact://1/1",
        "truncated": True,
    }
