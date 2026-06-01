from dimoo_run.core.events import AgentEvent
from dimoo_run.streaming.sse import encode_sse_event


def test_encode_sse_event_includes_id_event_and_json_payload() -> None:
    encoded = encode_sse_event(
        AgentEvent(
            type="agent.stream_chunk",
            payload={"delta": "hello"},
            run_id=1,
            sequence=1,
        )
    )

    assert "id: run_1:1" in encoded
    assert "event: agent.stream_chunk" in encoded
    assert 'data: {"delta":"hello"}' in encoded
    assert encoded.endswith("\n\n")
