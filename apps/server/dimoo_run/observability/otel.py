from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from dimoo_run.core.context import RuntimeContext

TRACE_KEYS = {"trace_id", "request_id", "correlation_id", "worker_id"}


@dataclass(frozen=True)
class RuntimeTraceContext:
    request_id: str
    trace_id: str
    correlation_id: str
    worker_id: str

    def as_payload_fields(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "worker_id": self.worker_id,
        }

    def as_log_fields(
        self,
        *,
        run_id: int,
        task_id: int | None,
        attempt_id: int | None,
    ) -> dict[str, Any]:
        return {
            **self.as_payload_fields(),
            "run_id": run_id,
            "task_id": task_id,
            "attempt_id": attempt_id,
        }


def ensure_trace_context(context: RuntimeContext, *, worker_id: str) -> RuntimeContext:
    request_id = context.request_id or f"req_run_{context.run_id}"
    trace_id = context.trace_id or f"trace_run_{context.run_id}"
    correlation_id = context.correlation_id or f"corr_task_{context.task_id or context.run_id}"
    metadata = {**context.metadata, "worker_id": worker_id}
    return RuntimeContext(
        tenant_id=context.tenant_id,
        project_id=context.project_id,
        run_id=context.run_id,
        task_id=context.task_id,
        agent_id=context.agent_id,
        agent_version_id=context.agent_version_id,
        deployment_id=context.deployment_id,
        user_id=context.user_id,
        service_account_id=context.service_account_id,
        thread_id=context.thread_id,
        session_id=context.session_id,
        request_id=request_id,
        attempt_id=context.attempt_id,
        trace_id=trace_id,
        correlation_id=correlation_id,
        idempotency_key=context.idempotency_key,
        environment=context.environment,
        framework=context.framework,
        adapter=context.adapter,
        agent_version=context.agent_version,
        deadline_at=context.deadline_at,
        permissions=list(context.permissions),
        secrets=dict(context.secrets),
        config=dict(context.config),
        metadata=metadata,
    )


def trace_context_from_runtime(context: RuntimeContext, *, worker_id: str) -> RuntimeTraceContext:
    enriched = ensure_trace_context(context, worker_id=worker_id)
    return RuntimeTraceContext(
        request_id=enriched.request_id or f"req_{uuid4().hex}",
        trace_id=enriched.trace_id or f"trace_{uuid4().hex}",
        correlation_id=enriched.correlation_id or f"corr_{uuid4().hex}",
        worker_id=worker_id,
    )


def attach_trace_fields(
    payload: dict[str, Any] | None,
    trace: RuntimeTraceContext,
) -> dict[str, Any]:
    merged = dict(payload or {})
    merged.update(trace.as_payload_fields())
    return merged


def redact_event_payload(payload: dict[str, Any], *, visibility_level: str) -> dict[str, Any]:
    if visibility_level == "public":
        return payload
    return {
        "redacted": True,
        **{key: value for key, value in payload.items() if key in TRACE_KEYS},
    }


def render_prometheus_metrics(snapshot: dict[str, Any]) -> str:
    summary = snapshot["summary"]
    queue_lines = [
        f'dimoorun_queue_backlog{{queue="{queue["queue"]}"}} {queue["queue_backlog"]}'
        for queue in snapshot["queues"]
    ]
    running_lines = [
        f'dimoorun_running_tasks{{queue="{queue["queue"]}"}} {queue["running_tasks"]}'
        for queue in snapshot["queues"]
    ]
    worker_lines = [
        (
            f'dimoorun_worker_heartbeat_age_seconds{{worker_id="{worker["worker_id"]}",'
            f' readiness="{worker["readiness"]}"}} '
            f'{0 if worker["heartbeat_age_seconds"] is None else worker["heartbeat_age_seconds"]}'
        )
        for worker in snapshot["workers"]
    ]
    lines = [
        "# HELP dimoorun_queue_backlog Runtime queue backlog by queue.",
        "# TYPE dimoorun_queue_backlog gauge",
        *queue_lines,
        "# HELP dimoorun_running_tasks Runtime running task count by queue.",
        "# TYPE dimoorun_running_tasks gauge",
        *running_lines,
        "# HELP dimoorun_worker_heartbeat_age_seconds Worker heartbeat age in seconds.",
        "# TYPE dimoorun_worker_heartbeat_age_seconds gauge",
        *worker_lines,
        "# HELP dimoorun_dead_letters_total Runtime dead-letter count.",
        "# TYPE dimoorun_dead_letters_total gauge",
        f'dimoorun_dead_letters_total {summary["dead_letters"]}',
        "# HELP dimoorun_retries_total Runtime retrying task count.",
        "# TYPE dimoorun_retries_total gauge",
        f'dimoorun_retries_total {summary["retries"]}',
        "# HELP dimoorun_run_latency_ms Runtime run latency percentiles.",
        "# TYPE dimoorun_run_latency_ms gauge",
        f'dimoorun_run_latency_ms{{quantile="0.95"}} {summary["p95_latency_ms"]}',
        f'dimoorun_run_latency_ms{{quantile="0.99"}} {summary["p99_latency_ms"]}',
        "# HELP dimoorun_active_incidents Runtime active incident count.",
        "# TYPE dimoorun_active_incidents gauge",
        f'dimoorun_active_incidents {summary["active_incidents"]}',
        "# HELP dimoorun_active_workers Runtime active worker count.",
        "# TYPE dimoorun_active_workers gauge",
        f'dimoorun_active_workers {summary["active_workers"]}',
        "",
    ]
    return "\n".join(lines)
