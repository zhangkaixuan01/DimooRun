from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from dimoo_run.observability.policies import RedactionPolicy, SamplingPolicy


@dataclass(frozen=True)
class TraceSpan:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: str
    tenant_id: str
    project_id: str | None
    run_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    latency_ms: int | None = None


class InMemoryTraceSink:
    def __init__(
        self,
        *,
        redaction_policy: RedactionPolicy | None = None,
        sampling_policy: SamplingPolicy | None = None,
    ) -> None:
        self.redaction_policy = redaction_policy or RedactionPolicy(fields=set())
        self.sampling_policy = sampling_policy or SamplingPolicy()
        self.spans: list[TraceSpan] = []

    def record(self, span: TraceSpan) -> TraceSpan | None:
        if not self.sampling_policy.should_sample(span.trace_id):
            return None
        stored = replace(span, metadata=self.redaction_policy.apply(span.metadata))
        self.spans.append(stored)
        return stored
