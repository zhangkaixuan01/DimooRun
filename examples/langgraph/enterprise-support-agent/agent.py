from __future__ import annotations

import operator
import os
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class EnterpriseSupportState(TypedDict, total=False):
    message: str
    customer_id: str
    order_id: str
    thread_id: str
    category: str
    risk_level: str
    requires_approval: bool
    approved: bool
    knowledge: dict[str, Any]
    order: dict[str, Any]
    answer: str
    tool_events: Annotated[list[dict[str, Any]], operator.add]
    model_events: Annotated[list[dict[str, Any]], operator.add]
    token_usage: dict[str, int]
    audit: Annotated[list[str], operator.add]


@tool
def search_support_knowledge(category: str) -> dict[str, Any]:
    """Search support policy snippets for a support category."""
    policies = {
        "billing": {
            "policy_id": "kb-billing-001",
            "summary": "Confirm invoice id, payment status, and account owner before refund guidance.",
        },
        "order": {
            "policy_id": "kb-order-001",
            "summary": "Check order status and carrier events before promising replacement or refund.",
        },
        "account-risk": {
            "policy_id": "kb-risk-001",
            "summary": "Destructive account actions require human approval and identity verification.",
        },
        "technical": {
            "policy_id": "kb-technical-001",
            "summary": "Collect request id, logs, timestamps, and reproduction steps before escalation.",
        },
    }
    return policies.get(category, policies["technical"])


@tool
def lookup_order_status(order_id: str) -> dict[str, Any]:
    """Look up the current order status in the commerce system."""
    if not order_id:
        return {"status": "missing_order_id", "next_step": "Ask the customer for an order id."}
    return {
        "order_id": order_id,
        "status": "in_review",
        "last_event": "Carrier handoff delayed; replacement eligibility requires supervisor review.",
    }


def classify(state: EnterpriseSupportState, config: RunnableConfig) -> dict[str, Any]:
    message = str(state.get("message", "")).strip()
    text = message.lower()
    configurable = config.get("configurable", {})
    thread_id = str(configurable.get("thread_id") or state.get("thread_id") or "enterprise-thread")

    if any(word in text for word in ("delete", "cancel account", "close workspace", "production")):
        category = "account-risk"
        risk_level = "high"
    elif any(word in text for word in ("refund", "invoice", "charge", "payment")):
        category = "billing"
        risk_level = "medium"
    elif any(word in text for word in ("order", "shipment", "delivery", "replacement")):
        category = "order"
        risk_level = "medium"
    else:
        category = "technical"
        risk_level = "low"

    return {
        "thread_id": thread_id,
        "category": category,
        "risk_level": risk_level,
        "requires_approval": risk_level == "high",
        "audit": [f"classified:{category}:{risk_level}:thread={thread_id}"],
    }


def call_tools(state: EnterpriseSupportState) -> dict[str, Any]:
    writer = get_stream_writer()
    category = str(state.get("category", "technical"))
    order_id = str(state.get("order_id", ""))

    knowledge = search_support_knowledge.invoke({"category": category})
    tool_events: list[dict[str, Any]] = [
        {
            "tool": "search_support_knowledge",
            "input": {"category": category},
            "output": knowledge,
        }
    ]
    update: dict[str, Any] = {
        "knowledge": knowledge,
        "tool_events": tool_events,
        "audit": [f"tool:search_support_knowledge:{category}"],
    }

    if category == "order" or order_id:
        order = lookup_order_status.invoke({"order_id": order_id})
        update["order"] = order
        update["tool_events"] = [
            *tool_events,
            {
                "tool": "lookup_order_status",
                "input": {"order_id": order_id},
                "output": order,
            },
        ]
        update["audit"] = [
            *update["audit"],
            f"tool:lookup_order_status:{order.get('status')}",
        ]

    writer({"phase": "tools", "category": category, "risk_level": state.get("risk_level")})
    return update


def draft_with_llm(state: EnterpriseSupportState) -> dict[str, Any]:
    writer = get_stream_writer()
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "enterprise-support-agent requires langchain-openai. "
            "Install this example's requirements.txt."
        ) from exc

    api_key = os.getenv("MODEL_GATEWAY_API_KEY")
    if not api_key:
        raise RuntimeError("MODEL_GATEWAY_API_KEY is required for enterprise-support-agent.")

    base_url = os.getenv("MODEL_GATEWAY_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_GATEWAY_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        temperature=0.2,
    )

    system = (
        "You are an enterprise customer support agent. "
        "Use only the provided policy and order context. "
        "Do not claim that a destructive action was completed. "
        "If approval is required, explain that a human reviewer must approve the action."
    )
    context = {
        "category": state.get("category"),
        "risk_level": state.get("risk_level"),
        "policy": state.get("knowledge"),
        "order": state.get("order"),
        "requires_approval": state.get("requires_approval"),
    }
    response = llm.invoke(
        [
            SystemMessage(content=system),
            HumanMessage(
                content=(
                    f"Customer message: {state.get('message')}\n"
                    f"Customer id: {state.get('customer_id', '')}\n"
                    f"Runtime context: {context}"
                )
            ),
        ]
    )
    usage = dict(getattr(response, "usage_metadata", None) or {})
    prompt_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    token_usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": int(usage.get("total_tokens") or prompt_tokens + completion_tokens),
    }
    response_metadata = dict(getattr(response, "response_metadata", None) or {})

    writer({"phase": "model", "model": model_name, "risk_level": state.get("risk_level")})
    return {
        "answer": str(response.content),
        "model_events": [
            {
                "provider": "openai_compatible",
                "model": model_name,
                "base_url": base_url,
                "response_metadata": response_metadata,
            }
        ],
        "token_usage": token_usage,
        "audit": [f"model:{model_name}"],
    }


def route_after_draft(state: EnterpriseSupportState) -> Literal["human_review", "finalize"]:
    return "human_review" if bool(state.get("requires_approval")) else "finalize"


def human_review(state: EnterpriseSupportState) -> Command[Literal["finalize", "__end__"]]:
    decision = interrupt(
        {
            "kind": "approval_required",
            "reason": "High-risk support action requires human review before responding.",
            "category": state.get("category"),
            "risk_level": state.get("risk_level"),
            "draft_answer": state.get("answer"),
            "expected_resume_payload": {
                "approved": True,
                "edited_answer": "optional reviewer-approved answer",
            },
        }
    )

    if not isinstance(decision, dict) or not decision.get("approved"):
        return Command(update={"approved": False, "audit": ["human_review:rejected"]}, goto=END)

    edited_answer = str(decision.get("edited_answer") or state.get("answer") or "")
    return Command(
        update={"approved": True, "answer": edited_answer, "audit": ["human_review:approved"]},
        goto="finalize",
    )


def finalize(state: EnterpriseSupportState) -> dict[str, Any]:
    return {
        "answer": str(state.get("answer", "")).strip(),
        "audit": ["finalized"],
    }


def build_graph(config: dict[str, Any] | None = None):
    """Return a compiled LangGraph graph for an enterprise support agent."""
    _ = config or {}
    builder = StateGraph(EnterpriseSupportState)
    builder.add_node("classify", classify)
    builder.add_node("call_tools", call_tools)
    builder.add_node("draft_with_llm", draft_with_llm)
    builder.add_node("human_review", human_review)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "call_tools")
    builder.add_edge("call_tools", "draft_with_llm")
    builder.add_conditional_edges(
        "draft_with_llm",
        route_after_draft,
        {
            "human_review": "human_review",
            "finalize": "finalize",
        },
    )
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=InMemorySaver())
