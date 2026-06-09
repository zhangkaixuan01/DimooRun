from collections.abc import AsyncIterator
from typing import Any

import pytest
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


class FakeResumeGraph:
    def __init__(self) -> None:
        self.input_data: Any | None = None
        self.config: dict[str, Any] | None = None

    async def ainvoke(self, input_data: Any, config: dict[str, Any]) -> dict[str, Any]:
        self.input_data = input_data
        self.config = config
        return {"resumed": True}


def make_context() -> RuntimeContext:
    return RuntimeContext(
        tenant_id=1,
        project_id=1,
        run_id=1,
        task_id=1,
        agent_id=1,
        agent_version_id="agent_version_1",
        deployment_id=1,
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
    assert graph.config["configurable"]["run_id"] == 1
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
async def test_langgraph_adapter_resume_uses_langgraph_command_with_runtime_context() -> None:
    pytest.importorskip("langgraph.types")
    adapter = LangGraphAdapter()
    graph = FakeResumeGraph()

    result = await adapter.resume(graph, 1, {"approved": True}, make_context())

    assert result.output == {"resumed": True}
    assert graph.input_data is not None
    assert graph.input_data.__class__.__name__ == "Command"
    assert graph.input_data.resume == {"approved": True}
    assert graph.config is not None
    assert graph.config["configurable"]["thread_id"] == "thread_1"
    assert graph.config["configurable"]["run_id"] == 1


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


def test_langgraph_adapter_certifies_checkpoint_and_resume() -> None:
    adapter = LangGraphAdapter()

    assert adapter.capabilities.checkpoint is True
    assert adapter.capabilities.resume is True
