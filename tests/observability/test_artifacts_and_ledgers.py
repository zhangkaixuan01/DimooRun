import pytest
from dimoo_run.artifacts.store import (
    ArtifactAccessDeniedError,
    ArtifactChecksumMismatchError,
    InMemoryArtifactStore,
)
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent
from dimoo_run.observability.audit import InMemoryComplianceAuditLog
from dimoo_run.observability.events import InMemoryEventSink
from dimoo_run.observability.metrics import MetricsRegistry
from dimoo_run.observability.policies import RedactionPolicy, SamplingPolicy
from dimoo_run.observability.traces import InMemoryTraceSink, TraceSpan


def context() -> RuntimeContext:
    return RuntimeContext(
        tenant_id=1,
        project_id=1,
        run_id=1,
        task_id=1,
        agent_id=1,
        agent_version_id="version_1",
        deployment_id=1,
        user_id="user_1",
        trace_id="trace_1",
        framework="langgraph",
        adapter="langgraph",
    )


def test_artifact_store_records_checksum_and_audits_reads_without_plaintext() -> None:
    audit_log = InMemoryComplianceAuditLog()
    store = InMemoryArtifactStore(audit_log=audit_log)
    artifact = store.write_json(
        context=context(),
        artifact_type="input_payload",
        payload={"question": "hello", "api_key": "sk-secret"},
        visibility_level="restricted",
        created_by="user_1",
    )

    assert artifact.storage_uri.startswith("memory://artifact/")
    assert artifact.size_bytes > 0
    assert artifact.checksum.startswith("sha256:")

    with pytest.raises(ArtifactAccessDeniedError):
        store.read_json(artifact.storage_uri, context=context(), permissions=set())

    payload = store.read_json(
        artifact.storage_uri,
        context=context(),
        permissions={"artifact:read:restricted"},
    )

    assert payload["question"] == "hello"
    assert "sk-secret" not in str(audit_log.records)
    assert [record.result for record in audit_log.records] == ["deny", "allow"]


def test_artifact_store_rejects_cross_scope_reads_even_with_permission() -> None:
    audit_log = InMemoryComplianceAuditLog()
    store = InMemoryArtifactStore(audit_log=audit_log)
    artifact = store.write_json(
        context=context(),
        artifact_type="output_payload",
        payload={"answer": "ok"},
        visibility_level="restricted",
        created_by="user_1",
    )
    other_context = RuntimeContext(
        tenant_id="tenant_2",
        project_id="project_2",
        run_id="run_2",
        task_id="task_2",
        agent_id="agent_2",
        agent_version_id="version_2",
        deployment_id="deployment_2",
        user_id="user_2",
        trace_id="trace_2",
        framework="langgraph",
        adapter="langgraph",
    )

    with pytest.raises(ArtifactAccessDeniedError):
        store.read_json(
            artifact.storage_uri,
            context=other_context,
            permissions={"artifact:read:restricted"},
        )

    assert audit_log.records[-1].result == "deny"
    assert audit_log.records[-1].metadata["reason"] == "scope_mismatch"


def test_artifact_store_verifies_checksum_on_read() -> None:
    audit_log = InMemoryComplianceAuditLog()
    store = InMemoryArtifactStore(audit_log=audit_log)
    artifact = store.write_json(
        context=context(),
        artifact_type="output_payload",
        payload={"answer": "ok"},
        visibility_level="restricted",
        created_by="user_1",
    )
    store._objects[artifact.storage_uri] = b'{"answer":"tampered"}'  # noqa: SLF001

    with pytest.raises(ArtifactChecksumMismatchError):
        store.read_json(
            artifact.storage_uri,
            context=context(),
            permissions={"artifact:read:restricted"},
        )

    assert audit_log.records[-1].result == "deny"
    assert audit_log.records[-1].metadata["reason"] == "checksum_mismatch"


def test_event_trace_and_audit_ledgers_are_separate_and_apply_redaction_sampling() -> None:
    event_sink = InMemoryEventSink(redaction_policy=RedactionPolicy(fields={"api_key"}))
    trace_sink = InMemoryTraceSink(
        redaction_policy=RedactionPolicy(fields={"api_key"}),
        sampling_policy=SamplingPolicy(sample_rate=0.0),
    )
    audit_log = InMemoryComplianceAuditLog()

    event_sink.emit(
        AgentEvent(
            type="model.completed",
            payload={"output": "ok", "api_key": "sk-secret"},
            sequence=1,
        ),
        context=context(),
    )
    trace_sink.record(
        TraceSpan(
            trace_id="trace_1",
            span_id="span_1",
            parent_span_id=None,
            name="model.call",
            kind="model",
            tenant_id=1,
            project_id=1,
            run_id=1,
            metadata={"api_key": "sk-secret"},
        )
    )
    audit_log.record(
        tenant_id=1,
        project_id=1,
        actor_id="user_1",
        actor_type="user",
        action="secret.read",
        resource_type="secret",
        resource_id="OPENAI_API_KEY",
        result="deny",
        metadata={"reason": "policy_denied", "api_key": "sk-secret"},
    )

    assert len(event_sink.events) == 1
    assert event_sink.events[0].payload["api_key"] == "[REDACTED]"
    assert trace_sink.spans == []
    assert len(audit_log.records) == 1
    assert audit_log.records[0].metadata["api_key"] == "[REDACTED]"


def test_redaction_policy_recursively_redacts_nested_secrets() -> None:
    policy = RedactionPolicy(fields={"api_key", "secret"})

    redacted = policy.apply(
        {
            "request": {
                "api_key": "sk-secret",
                "messages": [{"content": "hello", "secret": "nested-secret"}],
            }
        }
    )

    assert redacted["request"]["api_key"] == "[REDACTED]"
    assert redacted["request"]["messages"][0]["secret"] == "[REDACTED]"
    assert "sk-secret" not in str(redacted)
    assert "nested-secret" not in str(redacted)


def test_event_sink_rejects_events_without_sequence() -> None:
    sink = InMemoryEventSink()

    with pytest.raises(ValueError, match="event_sequence_required"):
        sink.emit(AgentEvent(type="model.completed", payload={}), context=context())


def test_metrics_registry_tracks_runtime_counters_and_gauges() -> None:
    metrics = MetricsRegistry()

    metrics.increment("run_total")
    metrics.increment("run_success_total")
    metrics.observe("run_latency_seconds", 1.25)
    metrics.set_gauge("task_queue_size", 3)

    snapshot = metrics.snapshot()
    assert snapshot.counters["run_total"] == 1
    assert snapshot.counters["run_success_total"] == 1
    assert snapshot.histograms["run_latency_seconds"] == [1.25]
    assert snapshot.gauges["task_queue_size"] == 3
