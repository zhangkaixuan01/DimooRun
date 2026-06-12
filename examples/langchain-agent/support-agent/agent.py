from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage


def build_agent(config: dict[str, Any] | None = None):
    runtime = config or {}
    message = str(
        runtime.get("agent_message") or "LangChain support-agent handled the request safely."
    )
    model = FakeMessagesListChatModel(responses=[AIMessage(content=message)])
    return create_agent(
        model,
        tools=[],
        system_prompt="You are a deterministic support triage agent for DimooRun smoke tests.",
        name="dimoorun-langchain-support-agent",
    )
