from typing import Any

import pytest
from dimoo_run.adapters.base.contract import CapabilityNotSupportedError
from dimoo_run.adapters.langchain_agent.adapter import LangChainAgentAdapter
from dimoo_run.core.context import RuntimeContext


class FakeRunnable:
    def __init__(self) -> None:
        self.config: dict[str, Any] | None = None

    async def ainvoke(self, input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        self.config = config
        return {"answer": input_data["question"]}


def make_context() -> RuntimeContext:
    return RuntimeContext(
        tenant_id=1,
        project_id=1,
        run_id=1,
        task_id=None,
        agent_id=1,
        agent_version_id="agent_version_1",
        deployment_id=None,
        user_id="user_1",
        service_account_id=None,
        thread_id=None,
    )


@pytest.mark.asyncio
async def test_langchain_agent_adapter_invoke_maps_metadata() -> None:
    runnable = FakeRunnable()
    adapter = LangChainAgentAdapter()

    result = await adapter.invoke(runnable, {"question": "hello"}, make_context())

    assert result.output == {"answer": "hello"}
    assert runnable.config is not None
    assert runnable.config["metadata"]["run_id"] == 1
    assert runnable.config["metadata"]["tenant_id"] == 1
    assert runnable.config["metadata"]["agent_version_id"] == "agent_version_1"


@pytest.mark.asyncio
async def test_langchain_agent_adapter_resume_is_not_supported() -> None:
    adapter = LangChainAgentAdapter()
    adapter.capabilities.resume = True

    with pytest.raises(CapabilityNotSupportedError) as exc_info:
        await adapter.resume(FakeRunnable(), "run_1", {"resume": "ok"}, make_context())

    assert exc_info.value.capability == "resume"
    assert exc_info.value.framework == "langchain-agent"


@pytest.mark.asyncio
async def test_langchain_agent_adapter_cancel_is_not_supported() -> None:
    adapter = LangChainAgentAdapter()

    with pytest.raises(CapabilityNotSupportedError) as exc_info:
        await adapter.cancel("run_1", make_context())

    assert exc_info.value.capability == "cancel"
    assert exc_info.value.framework == "langchain-agent"


def test_langchain_agent_adapter_maps_tool_callback_event() -> None:
    adapter = LangChainAgentAdapter()

    event = adapter.map_callback_event(
        kind="tool",
        name="search",
        payload={"input": "hello"},
    )

    assert event.type == "tool.called"
    assert event.framework == "langchain-agent"
    assert event.payload == {"name": "search", "input": "hello"}


def test_langchain_agent_adapter_maps_model_callback_event() -> None:
    adapter = LangChainAgentAdapter()

    event = adapter.map_callback_event(
        kind="model",
        name="openai",
        payload={"tokens": 12},
    )

    assert event.type == "model.started"
    assert event.payload == {"name": "openai", "tokens": 12}
# mypy: disable-error-code="arg-type"
