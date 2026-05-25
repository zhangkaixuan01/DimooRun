import json

from dimoo_run.core.events import AgentEvent


def encode_sse_event(event: AgentEvent) -> str:
    lines = []
    if event.event_id is not None:
        lines.append(f"id: {event.event_id}")
    lines.append(f"event: {event.type}")
    lines.append(f"data: {json.dumps(event.payload, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"
