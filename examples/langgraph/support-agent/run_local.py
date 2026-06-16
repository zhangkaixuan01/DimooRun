from __future__ import annotations

from agent import build_graph
from langgraph.types import Command


def main() -> None:
    graph = build_graph({})
    config = {"configurable": {"thread_id": "support-demo-thread"}}

    normal = graph.invoke(
        {"message": "The checkout page failed with a timeout."},
        config,
    )
    print("normal answer:")
    print(normal["answer"])

    print("\nstream updates:")
    for chunk in graph.stream(
        {"message": "Please cancel this production account."},
        config,
        stream_mode="updates",
    ):
        print(chunk)

    interrupted = graph.invoke(
        {"message": "Please delete my production workspace."},
        {"configurable": {"thread_id": "approval-thread"}},
    )
    print("\ninterrupt payload:")
    print(interrupted.get("__interrupt__"))

    resumed = graph.invoke(
        Command(
            resume={
                "approved": True,
                "edited_answer": (
                    "Approved response: we can start a controlled deletion workflow "
                    "after identity verification."
                ),
            }
        ),
        {"configurable": {"thread_id": "approval-thread"}},
    )
    print("\nresumed answer:")
    print(resumed["answer"])


if __name__ == "__main__":
    main()
