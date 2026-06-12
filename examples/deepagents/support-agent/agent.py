from __future__ import annotations

import types
from typing import Any

import langchain.chat_models as langchain_chat_models
from deepagents import _models as deepagents_models
from deepagents import create_deep_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage


class _PatchedInitChatModel:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model
        self.original = deepagents_models.init_chat_model
        self.original_base_chat_model = langchain_chat_models.BaseChatModel
        self.original_deepagents_base_chat_model = deepagents_models.BaseChatModel

    def __enter__(self) -> None:
        model = self.model
        original = self.original

        def patched_init_chat_model(spec: str | None = None, **kwargs: Any) -> BaseChatModel:
            _ = kwargs
            if spec == "dimoorun:deterministic":
                return model
            return original(spec, **kwargs)

        deepagents_models.init_chat_model = patched_init_chat_model
        langchain_chat_models.BaseChatModel = model.__class__
        deepagents_models.BaseChatModel = model.__class__

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = exc_type, exc, tb
        deepagents_models.init_chat_model = self.original
        langchain_chat_models.BaseChatModel = self.original_base_chat_model
        deepagents_models.BaseChatModel = self.original_deepagents_base_chat_model


def build_agent(config: dict[str, Any] | None = None):
    runtime = config or {}
    prefix = str(runtime.get("response_prefix") or "DeepAgents support-agent")
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(content=f"{prefix}: Check the tenant policy"),
            AIMessage(content=f"{prefix}: Stream the tenant answer"),
        ]
    )
    object.__setattr__(
        model,
        "bind_tools",
        types.MethodType(lambda self, tools, **kwargs: self, model),
    )
    with _PatchedInitChatModel(model):
        return create_deep_agent(
            model="dimoorun:deterministic",
            tools=[],
            subagents=[],
            permissions=[],
            name="dimoorun-deepagents-support-agent",
        )
