import pytest
from dimoo_run.adapters.base.capabilities import CapabilityModel
from dimoo_run.adapters.base.contract import CapabilityNotSupportedError
from dimoo_run.adapters.base.versioning import (
    ADAPTER_API_VERSION,
    AdapterVersionInfo,
    CompatibilityStatus,
    check_adapter_compatibility,
)
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult


def test_runtime_context_contains_platform_execution_identity() -> None:
    context = RuntimeContext(
        tenant_id="tenant_1",
        project_id="project_1",
        run_id="run_1",
        task_id="task_1",
        agent_id="agent_1",
        agent_version_id="agent_version_1",
        deployment_id="deployment_1",
        user_id=None,
        service_account_id="svc_1",
        thread_id="thread_1",
        session_id="session_1",
        request_id="req_1",
        attempt_id="attempt_1",
        trace_id="trace_1",
        correlation_id="correlation_1",
        idempotency_key="idem_1",
        environment="dev",
        framework="langgraph",
        adapter="langgraph",
        agent_version="0.1.0",
        permissions=["ticket.write"],
        secrets={"OPENAI_API_KEY": "secret-ref"},
        config={"temperature": 0},
        metadata={"source": "test"},
    )

    assert context.run_id == "run_1"
    assert context.thread_id == "thread_1"
    assert context.to_metadata()["tenant_id"] == "tenant_1"
    assert context.to_metadata()["request_id"] == "req_1"
    assert context.to_metadata()["trace_id"] == "trace_1"
    assert context.to_metadata()["idempotency_key"] == "idem_1"
    assert context.to_metadata()["metadata"] == {"source": "test"}
    assert "deadline_at" not in context.to_metadata()


def test_runtime_context_metadata_cannot_override_platform_identity() -> None:
    context = RuntimeContext(
        tenant_id="tenant_1",
        project_id="project_1",
        run_id="run_1",
        task_id=None,
        agent_id="agent_1",
        agent_version_id="agent_version_1",
        deployment_id=None,
        metadata={"tenant_id": "spoofed", "run_id": "spoofed"},
    )

    metadata = context.to_metadata()

    assert metadata["tenant_id"] == "tenant_1"
    assert metadata["run_id"] == "run_1"
    assert metadata["metadata"] == {"tenant_id": "spoofed", "run_id": "spoofed"}


def test_runtime_context_metadata_can_include_none_values_when_requested() -> None:
    context = RuntimeContext(
        tenant_id="tenant_1",
        project_id=None,
        run_id="run_1",
        task_id=None,
        agent_id="agent_1",
        agent_version_id="agent_version_1",
        deployment_id=None,
    )

    metadata = context.to_metadata(include_none=True)

    assert metadata["project_id"] is None
    assert metadata["task_id"] is None


def test_agent_result_and_event_have_stable_shapes() -> None:
    event = AgentEvent(
        type="agent.stream_chunk",
        payload={"delta": "hello"},
        run_id="run_1",
        sequence=1,
    )
    result = AgentResult(output={"message": "done"}, events=[event], metadata={"latency_ms": 10})

    assert result.output["message"] == "done"
    assert result.events[0].type == "agent.stream_chunk"
    assert result.events[0].event_id == "run_1:1"
    assert result.metadata["latency_ms"] == 10


def test_capability_negative_error_is_stable() -> None:
    capabilities = CapabilityModel(invoke=True, stream=False)

    with pytest.raises(CapabilityNotSupportedError) as exc_info:
        capabilities.require("stream", framework="langchain-agent")

    assert exc_info.value.error_code == "capability_not_supported"
    assert exc_info.value.capability == "stream"
    assert exc_info.value.framework == "langchain-agent"
    assert exc_info.value.to_error_response() == {
        "error": "capability_not_supported",
        "capability": "stream",
        "framework": "langchain-agent",
    }


def test_adapter_version_compatibility_status() -> None:
    assert (
        check_adapter_compatibility(
            expected_adapter_api_version=ADAPTER_API_VERSION,
            actual_adapter_api_version=ADAPTER_API_VERSION,
        )
        == CompatibilityStatus.compatible
    )
    assert (
        check_adapter_compatibility(
            expected_adapter_api_version="0.9",
            actual_adapter_api_version=ADAPTER_API_VERSION,
        )
        == CompatibilityStatus.migration_required
    )


def test_adapter_version_info_checked_at_uses_fresh_timestamp() -> None:
    first = AdapterVersionInfo(framework="langgraph", framework_version="1.2.1")
    second = AdapterVersionInfo(framework="langgraph", framework_version="1.2.1")

    assert first.checked_at is not second.checked_at
