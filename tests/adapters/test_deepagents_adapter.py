from typing import Any

import pytest
from dimoo_run.adapters.base.contract import CapabilityNotSupportedError
from dimoo_run.adapters.deepagents.adapter import DeepAgentsAdapter
from dimoo_run.core.context import RuntimeContext


class FakeDeepAgent:
    def __init__(self) -> None:
        self.config: dict[str, Any] | None = None

    async def ainvoke(self, input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        self.config = config
        return {"result": input_data["task"]}


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
        config={"sandbox": "readonly"},
    )


def test_deepagents_adapter_declares_filesystem_and_subagent_capabilities() -> None:
    adapter = DeepAgentsAdapter()

    assert adapter.capabilities.filesystem is True
    assert adapter.capabilities.subagents is True
    assert adapter.capabilities.checkpoint is False
    assert adapter.capabilities.resume is False


@pytest.mark.asyncio
async def test_deepagents_adapter_invoke_injects_runtime_context() -> None:
    agent = FakeDeepAgent()
    adapter = DeepAgentsAdapter()

    result = await adapter.invoke(agent, {"task": "plan"}, make_context())

    assert result.output == {"result": "plan"}
    assert agent.config is not None
    assert agent.config["metadata"]["run_id"] == 1
    assert agent.config["configurable"]["thread_id"] == "thread_1"
    assert agent.config["runtime_context"]["agent_id"] == 1


def test_deepagents_adapter_rejects_filesystem_when_capability_disabled() -> None:
    adapter = DeepAgentsAdapter()
    adapter.capabilities.filesystem = False

    with pytest.raises(CapabilityNotSupportedError):
        adapter.require_filesystem_access()


def test_deepagents_adapter_maps_filesystem_event() -> None:
    adapter = DeepAgentsAdapter()

    event = adapter.map_runtime_event("filesystem.updated", {"path": "/tmp/result.txt"})

    assert event.type == "framework.deepagents.filesystem.updated"
    assert event.framework == "deepagents"
    assert event.payload == {"path": "/tmp/result.txt"}


@pytest.mark.asyncio
async def test_deepagents_adapter_resume_is_not_certified_in_contract_scaffold() -> None:
    adapter = DeepAgentsAdapter()

    with pytest.raises(CapabilityNotSupportedError):
        await adapter.resume(FakeDeepAgent(), "run_1", {"resume": "ok"}, make_context())
