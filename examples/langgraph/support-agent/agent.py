from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class SupportAgentState(TypedDict, total=False):
    message: str
    thread_id: str
    category: str
    priority: str
    needs_approval: bool
    approved: bool
    answer: str
    tool_events: Annotated[list[dict[str, Any]], operator.add]
    model_events: Annotated[list[dict[str, Any]], operator.add]
    token_usage: dict[str, int]
    audit: Annotated[list[str], operator.add]


def classify(state: SupportAgentState, config: RunnableConfig) -> dict[str, Any]:
    message = str(state.get("message", "")).strip()
    text = message.lower()
    configurable = config.get("configurable", {})
    thread_id = str(configurable.get("thread_id") or state.get("thread_id") or "local-thread")

    if any(word in text for word in ("delete", "refund", "cancel", "production", "prod")):
        category = "account-risk"
        priority = "high"
        needs_approval = True
    elif any(word in text for word in ("error", "failed", "bug", "timeout")):
        category = "technical-support"
        priority = "medium"
        needs_approval = False
    else:
        category = "general-support"
        priority = "low"
        needs_approval = False

    return {
        "thread_id": thread_id,
        "category": category,
        "priority": priority,
        "needs_approval": needs_approval,
        "audit": [f"classified:{category}:{priority}:thread={thread_id}"],
    }


def retrieve_policy(state: SupportAgentState) -> dict[str, Any]:
    category = str(state.get("category", "general-support"))
    policy = {
        "account-risk": "Require human approval before suggesting destructive account actions.",
        "technical-support": "Ask for logs, request id, and reproduction steps before escalation.",
        "general-support": "Answer directly and provide one concrete next step.",
    }[category]

    return {
        "tool_events": [
            {
                "tool": "policy_lookup",
                "input": {"category": category},
                "output": {"policy": policy},
            }
        ],
        "audit": [f"tool:policy_lookup:{category}"],
    }


def draft_answer(state: SupportAgentState) -> dict[str, Any]:
    writer = get_stream_writer()
    category = str(state.get("category", "general-support"))
    priority = str(state.get("priority", "low"))
    message = str(state.get("message", ""))
    policy = state.get("tool_events", [{}])[-1].get("output", {}).get("policy", "")

    writer({"phase": "draft", "category": category, "priority": priority})

    answer = (
        f"Category: {category}. Priority: {priority}. "
        f"Policy: {policy} "
        f"Response: I received your request: {message!r}. "
        "Please share any relevant request id or error detail so the next action is auditable."
    )
    prompt_tokens = max(1, len(message.split()) + len(policy.split()))
    completion_tokens = max(1, len(answer.split()))

    return {
        "answer": answer,
        "model_events": [
            {
                "model": "deterministic-support-drafter",
                "input_chars": len(message),
                "output_chars": len(answer),
            }
        ],
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "audit": ["model:draft_answer"],
    }


def route_after_draft(state: SupportAgentState) -> Literal["human_review", "finalize"]:
    return "human_review" if bool(state.get("needs_approval")) else "finalize"


def human_review(state: SupportAgentState) -> Command[Literal["finalize", "__end__"]]:
    decision = interrupt(
        {
            "kind": "approval_required",
            "reason": "High-risk support action requires human review.",
            "category": state.get("category"),
            "priority": state.get("priority"),
            "draft_answer": state.get("answer"),
            "expected_resume_payload": {
                "approved": True,
                "edited_answer": "optional replacement answer",
            },
        }
    )

    if not isinstance(decision, dict) or not decision.get("approved"):
        return Command(
            update={
                "approved": False,
                "audit": ["human_review:rejected"],
            },
            goto=END,
        )

    edited_answer = str(decision.get("edited_answer") or state.get("answer") or "")
    return Command(
        update={
            "approved": True,
            "answer": edited_answer,
            "audit": ["human_review:approved"],
        },
        goto="finalize",
    )


def finalize(state: SupportAgentState) -> dict[str, Any]:
    answer = str(state.get("answer", ""))
    suffix = "\n\nDimooRun trace: response was produced by the LangGraph support-agent example."
    return {
        "answer": f"{answer}{suffix}",
        "audit": ["finalized"],
    }


def build_graph(config: dict[str, Any] | None = None):
    """Return a compiled LangGraph graph for DimooRun's LangGraphAdapter."""
    _ = config or {}
    checkpointer = InMemorySaver()
    builder = StateGraph(SupportAgentState)
    builder.add_node("classify", classify)
    builder.add_node("retrieve_policy", retrieve_policy)
    builder.add_node("draft_answer", draft_answer)
    builder.add_node("human_review", human_review)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "retrieve_policy")
    builder.add_edge("retrieve_policy", "draft_answer")
    builder.add_conditional_edges(
        "draft_answer",
        route_after_draft,
        {
            "human_review": "human_review",
            "finalize": "finalize",
        },
    )
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer)
