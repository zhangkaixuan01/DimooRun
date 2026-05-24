import inspect
from collections.abc import AsyncIterator
from typing import Any

from dimoo_run.core.context import RuntimeContext


def runtime_config(configurable: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "configurable": configurable,
        "metadata": metadata,
    }


def context_metadata(context: RuntimeContext) -> dict[str, Any]:
    return context.to_metadata()


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def call_invoke(agent: Any, input_data: dict[str, Any], config: dict[str, Any]) -> Any:
    if hasattr(agent, "ainvoke"):
        return await maybe_await(agent.ainvoke(input_data, config))
    if hasattr(agent, "invoke"):
        return await maybe_await(agent.invoke(input_data, config))
    if callable(agent):
        return await maybe_await(agent(input_data, config))
    raise TypeError("Agent does not expose invoke, ainvoke, or callable interface.")


async def iterate_stream(
    agent: Any,
    input_data: dict[str, Any],
    config: dict[str, Any],
) -> AsyncIterator[Any]:
    if hasattr(agent, "astream"):
        stream = agent.astream(input_data, config)
    elif hasattr(agent, "stream"):
        stream = agent.stream(input_data, config)
    else:
        raise TypeError("Agent does not expose stream or astream interface.")

    if hasattr(stream, "__aiter__"):
        async for chunk in stream:
            yield chunk
    else:
        for chunk in stream:
            yield chunk
