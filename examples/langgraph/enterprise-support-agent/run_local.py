from __future__ import annotations

from agent import build_graph


def main() -> None:
    graph = build_graph({})
    result = graph.invoke(
        {
            "message": "My order is delayed and I need a replacement.",
            "customer_id": "cus_123",
            "order_id": "ord_456",
        },
        {"configurable": {"thread_id": "enterprise-support-demo"}},
    )
    print(result["answer"])
    print(result.get("token_usage"))


if __name__ == "__main__":
    main()
