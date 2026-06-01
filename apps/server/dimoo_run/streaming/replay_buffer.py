import json
from dataclasses import replace
from typing import Any

from dimoo_run.core.events import AgentEvent


class ReplayExpiredError(RuntimeError):
    def __init__(self, event: AgentEvent) -> None:
        self.event = event
        super().__init__("stream_replay_expired")


class ReplayBuffer:
    def __init__(self, *, max_events_per_run: int = 1000, max_payload_bytes: int = 64_000) -> None:
        self.max_events_per_run = max_events_per_run
        self.max_payload_bytes = max_payload_bytes
        self._events: dict[int, list[AgentEvent]] = {}
        self._next_sequence: dict[int, int] = {}

    def append(self, run_id: int, attempt_id: int | None, event: AgentEvent) -> AgentEvent:
        sequence = self._next_sequence.get(run_id, 1)
        payload = self._payload_or_ref(run_id, sequence, event.payload)
        stored = replace(
            event,
            run_id=run_id,
            attempt_id=attempt_id,
            sequence=sequence,
            event_id=f"{run_id}:{sequence}",
            payload=payload,
        )
        events = self._events.setdefault(run_id, [])
        events.append(stored)
        if len(events) > self.max_events_per_run:
            del events[: len(events) - self.max_events_per_run]
        self._next_sequence[run_id] = sequence + 1
        return stored

    def replay(self, run_id: int, last_event_id: str | None = None) -> list[AgentEvent]:
        events = list(self._events.get(run_id, []))
        if last_event_id is None:
            return events
        last_sequence = self._parse_event_id(run_id, last_event_id)
        if events and events[0].sequence is not None and last_sequence < events[0].sequence:
            expired = AgentEvent(
                type="stream.replay_expired",
                payload={"last_event_id": last_event_id},
                run_id=run_id,
                event_id=f"{run_id}:replay-expired:{last_sequence}",
                visibility_level="transport",
            )
            raise ReplayExpiredError(expired)
        return [
            event
            for event in events
            if event.sequence is not None and event.sequence > last_sequence
        ]

    def _payload_or_ref(
        self,
        run_id: int,
        sequence: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        if len(encoded) <= self.max_payload_bytes:
            return payload
        return {
            "payload_ref": f"artifact://{run_id}/{sequence}",
            "truncated": True,
        }

    def _parse_event_id(self, run_id: int, event_id: str) -> int:
        prefix = f"{run_id}:"
        if not event_id.startswith(prefix):
            raise ValueError("Last-Event-ID does not match run_id")
        return int(event_id[len(prefix) :])
