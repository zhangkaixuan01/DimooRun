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


class LangGraphAdapter:
    framework = "langgraph"

    def __init__(self) -> None:
        self.capabilities = CapabilityModel(
            invoke=True,
            stream=True,
            checkpoint=True,
            resume=True,
            interrupt=True,
            human_in_loop=True,
            tool_events=True,
            model_events=True,
            token_usage=True,
        )

    def version_info(self) -> AdapterVersionInfo:
        return build_version_info(framework=self.framework, package_name="langgraph")

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
            payload = chunk if isinstance(chunk, dict) else {"chunk": chunk}
            event_type = "agent.stream_chunk"
            if "__interrupt__" in payload:
                event_type = "human_interrupt.required"
                interrupt_payload = payload["__interrupt__"]
                payload = interrupt_payload if isinstance(interrupt_payload, dict) else payload
            yield AgentEvent(
                type=event_type,
                payload=payload,
                run_id=context.run_id,
                sequence=sequence,
                framework=self.framework,
            )

    async def resume(
        self,
        agent: Any,
        run_id: int,
        payload: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        self.capabilities.require("resume", self.framework)
        _ = run_id
        try:
            from langgraph.types import Command
        except ImportError as exc:  # pragma: no cover - dependency wiring issue
            raise CapabilityNotSupportedError(
                capability="resume",
                framework=self.framework,
            ) from exc

        output = await call_invoke(agent, Command(resume=payload), self._config(context))
        return AgentResult(output=output if isinstance(output, dict) else {"output": output})

    async def cancel(self, run_id: int, context: RuntimeContext) -> None:
        self.capabilities.require("interrupt", self.framework)
        _ = run_id, context

    def _config(self, context: RuntimeContext) -> dict[str, Any]:
        configurable = {
            "thread_id": context.thread_id,
            "run_id": context.run_id,
            "task_id": context.task_id,
        }
        return runtime_config(configurable=configurable, metadata=context_metadata(context))
