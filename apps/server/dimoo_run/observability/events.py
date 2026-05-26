from dataclasses import replace

from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent
from dimoo_run.observability.policies import RedactionPolicy


class InMemoryEventSink:
    def __init__(self, *, redaction_policy: RedactionPolicy | None = None) -> None:
        self.redaction_policy = redaction_policy or RedactionPolicy(fields=set())
        self.events: list[AgentEvent] = []

    def emit(self, event: AgentEvent, *, context: RuntimeContext) -> AgentEvent:
        if event.sequence is None:
            raise ValueError("event_sequence_required")
        stored = replace(
            event,
            run_id=event.run_id or context.run_id,
            attempt_id=event.attempt_id or context.attempt_id,
            framework=event.framework or context.framework,
            payload=self.redaction_policy.apply(event.payload),
        )
        self.events.append(stored)
        return stored
