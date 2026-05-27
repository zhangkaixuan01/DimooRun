from dataclasses import dataclass, field
from typing import Any, Protocol

from dimoo_run.core.events import AgentEvent
from dimoo_run.observability.audit import ComplianceAuditRecord
from dimoo_run.observability.policies import RedactionPolicy, SamplingPolicy


class ExportSink(Protocol):
    def send(self, payload: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class ExporterConfig:
    name: str
    kind: str
    enabled: bool = True


@dataclass(frozen=True)
class ExportFailure:
    exporter: str
    payload_type: str
    reason: str
    payload: dict[str, Any]


class ObservabilityExporter:
    def __init__(
        self,
        *,
        config: ExporterConfig,
        sink: ExportSink,
        redaction_policy: RedactionPolicy | None = None,
        sampling_policy: SamplingPolicy | None = None,
    ) -> None:
        self.config = config
        self.sink = sink
        self.redaction_policy = redaction_policy or RedactionPolicy(fields={"secret", "api_key"})
        self.sampling_policy = sampling_policy or SamplingPolicy()
        self.failures: list[ExportFailure] = []
        self.delivered: list[dict[str, Any]] = []

    def export_event(self, event: AgentEvent) -> bool:
        trace_id = event.event_id or event.run_id or event.type
        if not self.config.enabled or not self.sampling_policy.should_sample(trace_id):
            return False
        return self._send(
            payload_type="event",
            payload={
                "ledger": "event",
                "type": event.type,
                "run_id": event.run_id,
                "attempt_id": event.attempt_id,
                "sequence": event.sequence,
                "event_id": event.event_id,
                "payload": event.payload,
            },
        )

    def export_audit(self, record: ComplianceAuditRecord) -> bool:
        if not self.config.enabled:
            return False
        return self._send(
            payload_type="audit",
            payload={
                "ledger": "audit",
                "action": record.action,
                "resource_type": record.resource_type,
                "resource_id": record.resource_id,
                "result": record.result,
                "metadata": record.metadata,
            },
        )

    def _send(self, *, payload_type: str, payload: dict[str, Any]) -> bool:
        redacted = self.redaction_policy.apply(payload)
        try:
            self.sink.send(redacted)
        except Exception as exc:  # noqa: BLE001
            self.failures.append(
                ExportFailure(
                    exporter=self.config.name,
                    payload_type=payload_type,
                    reason=str(exc),
                    payload=redacted,
                )
            )
            return False
        self.delivered.append(redacted)
        return True


@dataclass
class InMemoryExportSink:
    payloads: list[dict[str, Any]] = field(default_factory=list)
    fail_next: bool = False

    def send(self, payload: dict[str, Any]) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("export_sink_failed")
        self.payloads.append(payload)
