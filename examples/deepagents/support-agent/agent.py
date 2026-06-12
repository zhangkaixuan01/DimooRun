from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from deepagents import create_deep_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class DeterministicDeepAgentModel(BaseChatModel):
    response_prefix: str = "DeepAgents support-agent"

    @property
    def _llm_type(self) -> str:
        return "dimoorun-deterministic-deepagents"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        _ = stop, run_manager, kwargs
        content = messages[-1].content if messages else "no-input"
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content=f"{self.response_prefix}: {content}"),
                )
            ]
        )

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> DeterministicDeepAgentModel:
        _ = tools, tool_choice, kwargs
        return self


def build_agent(config: dict[str, Any] | None = None):
    runtime = config or {}
    prefix = str(runtime.get("response_prefix") or "DeepAgents support-agent")
    return create_deep_agent(
        model=DeterministicDeepAgentModel(response_prefix=prefix),
        tools=[],
        subagents=[],
        permissions=[],
        name="dimoorun-deepagents-support-agent",
    )
