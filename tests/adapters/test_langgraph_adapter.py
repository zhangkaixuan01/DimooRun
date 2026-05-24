from collections.abc import AsyncIterator
from typing import Any

import pytest
from dimoo_run.adapters.base.contract import CapabilityNotSupportedError
from dimoo_run.adapters.langgraph.adapter import LangGraphAdapter
from dimoo_run.core.context import RuntimeContext


class FakeGraph:
    def __init__(self) -> None:
        self.config: dict[str, Any] | None = None

    async def ainvoke(self, input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        self.config = config
        return {"echo": input_data["message"]}

    async def astream(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        self.config = config
        yield {"delta": input_data["message"]}


class FakeInterruptGraph:
    async def astream(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        _ = input_data, config
        yield {"__interrupt__": {"reason": "approval_required"}}


def make_context() -> RuntimeContext:
    return RuntimeContext(
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
    )


@pytest.mark.asyncio
async def test_langgraph_adapter_invoke_maps_runtime_context_to_configurable() -> None:
    graph = FakeGraph()
    adapter = LangGraphAdapter()

    result = await adapter.invoke(graph, {"message": "hello"}, make_context())

    assert result.output == {"echo": "hello"}
    assert graph.config is not None
    assert graph.config["configurable"]["thread_id"] == "thread_1"
    assert graph.config["configurable"]["run_id"] == "run_1"
    assert graph.config["metadata"]["agent_version_id"] == "agent_version_1"


@pytest.mark.asyncio
async def test_langgraph_adapter_stream_maps_chunks_to_agent_events() -> None:
    adapter = LangGraphAdapter()

    events = [
        event async for event in adapter.stream(FakeGraph(), {"message": "hello"}, make_context())
    ]

    assert len(events) == 1
    assert events[0].type == "agent.stream_chunk"
    assert events[0].payload == {"delta": "hello"}
    assert events[0].framework == "langgraph"


@pytest.mark.asyncio
async def test_langgraph_adapter_resume_is_not_certified_in_contract_scaffold() -> None:
    adapter = LangGraphAdapter()

    with pytest.raises(CapabilityNotSupportedError):
        await adapter.resume(FakeGraph(), "run_1", {"resume": "ok"}, make_context())


@pytest.mark.asyncio
async def test_langgraph_adapter_maps_interrupt_chunks() -> None:
    adapter = LangGraphAdapter()

    events = [
        event
        async for event in adapter.stream(
            FakeInterruptGraph(), {"message": "hello"}, make_context()
        )
    ]

    assert events[0].type == "human_interrupt.required"
    assert events[0].payload == {"reason": "approval_required"}


def test_langgraph_adapter_does_not_certify_checkpoint_or_resume() -> None:
    adapter = LangGraphAdapter()

    assert adapter.capabilities.checkpoint is False
    assert adapter.capabilities.resume is False
