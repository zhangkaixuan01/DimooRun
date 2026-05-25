from collections.abc import AsyncIterator
from typing import Any

from dimoo_run.adapters.base.capabilities import CapabilityModel
from dimoo_run.adapters.base.contract import CapabilityNotSupportedError
from dimoo_run.adapters.base.utils import (
    call_invoke,
    context_metadata,
    iterate_stream,
    runtime_config,
)
from dimoo_run.adapters.base.versioning import AdapterVersionInfo, build_version_info
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult
from dimoo_run.packages.loader import load_entrypoint_result


class LangChainAgentAdapter:
    framework = "langchain-agent"

    def __init__(self) -> None:
        self.capabilities = CapabilityModel(
            invoke=True,
            stream=True,
            tool_events=True,
            model_events=True,
            token_usage=True,
        )

    def version_info(self) -> AdapterVersionInfo:
        return build_version_info(framework=self.framework, package_name="langchain")

    async def load(
        self,
        package_uri: str,
        manifest: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> Any:
        return load_entrypoint_result(
            package_uri,
            manifest["runtime"]["entrypoint"],
            runtime_config,
        )

    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        self.capabilities.require("invoke", self.framework)
        output = await call_invoke(agent, input_data, self._config(context))
        return AgentResult(output=output if isinstance(output, dict) else {"output": output})

    async def stream(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AsyncIterator[AgentEvent]:
        self.capabilities.require("stream", self.framework)
        sequence = 0
        async for chunk in iterate_stream(agent, input_data, self._config(context)):
            sequence += 1
            yield AgentEvent(
                type="agent.stream_chunk",
                payload=chunk if isinstance(chunk, dict) else {"chunk": chunk},
                run_id=context.run_id,
                sequence=sequence,
                framework=self.framework,
            )

    async def resume(
        self,
        agent: Any,
        run_id: str,
        payload: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        _ = agent, run_id, payload, context
        raise CapabilityNotSupportedError(capability="resume", framework=self.framework)

    async def cancel(self, run_id: str, context: RuntimeContext) -> None:
        _ = run_id, context
        raise CapabilityNotSupportedError(capability="cancel", framework=self.framework)

    def map_callback_event(self, kind: str, name: str, payload: dict[str, Any]) -> AgentEvent:
        event_type = {
            "tool": "tool.called",
            "model": "model.started",
        }.get(kind, f"framework.langchain.callback.{kind}")
        return AgentEvent(
            type=event_type,
            payload={"name": name, **payload},
            framework=self.framework,
        )

    def _config(self, context: RuntimeContext) -> dict[str, Any]:
        return runtime_config(configurable={}, metadata=context_metadata(context))
