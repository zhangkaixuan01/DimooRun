from collections.abc import AsyncIterator
from typing import Any, Protocol

from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult


class CapabilityNotSupportedError(RuntimeError):
    error_code = "capability_not_supported"

    def __init__(self, capability: str, framework: str) -> None:
        self.capability = capability
        self.framework = framework
        super().__init__(f"{framework} does not support capability {capability}.")

    def to_error_response(self) -> dict[str, str]:
        return {
            "error": self.error_code,
            "capability": self.capability,
            "framework": self.framework,
        }


class AgentAdapter(Protocol):
    framework: str

    async def load(
        self,
        package_uri: str,
        manifest: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> Any: ...

    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult: ...

    async def stream(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AsyncIterator[AgentEvent]: ...

    async def resume(
        self,
        agent: Any,
        run_id: str,
        payload: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult: ...

    async def cancel(self, run_id: str, context: RuntimeContext) -> None: ...
