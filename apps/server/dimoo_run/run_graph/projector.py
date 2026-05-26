from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from dimoo_run.core.events import AgentEvent


@dataclass
class RunGraphNode:
    id: str
    run_id: str
    attempt_id: str | None
    node_key: str
    node_type: str
    name: str
    status: str
    framework_node_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latency_ms: int | None = None
    input_ref: str | None = None
    output_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunGraphEdge:
    id: str
    run_id: str
    source_node_key: str
    target_node_key: str
    source_node_id: str | None
    target_node_id: str | None
    edge_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunGraph:
    run_id: str
    attempt_id: str | None
    nodes: list[RunGraphNode]
    edges: list[RunGraphEdge]


class RunGraphProjector:
    def project(
        self,
        *,
        run_id: str,
        attempt_id: str | None,
        events: list[AgentEvent],
    ) -> RunGraph:
        nodes: dict[str, RunGraphNode] = {}
        edges: list[RunGraphEdge] = []
        for event in events:
            node_key = str(event.payload.get("node_key") or event.type)
            node = nodes.get(node_key)
            if node is None:
                node = RunGraphNode(
                    id=str(uuid4()),
                    run_id=run_id,
                    attempt_id=attempt_id,
                    node_key=node_key,
                    node_type=self._node_type(event.type),
                    name=str(event.payload.get("name") or node_key),
                    status="running" if event.type.endswith(".started") else "succeeded",
                    input_ref=event.payload.get("input_ref"),
                    output_ref=event.payload.get("output_ref"),
                    metadata={"source_event_type": event.type},
                )
                nodes[node_key] = node
            if event.type.endswith(".completed"):
                node.status = "succeeded"
                node.output_ref = event.payload.get("output_ref", node.output_ref)
                node.latency_ms = event.payload.get("latency_ms", node.latency_ms)
            parent_node_key = event.payload.get("parent_node_key")
            if parent_node_key is not None:
                parent_key = str(parent_node_key)
                parent_node = nodes.get(parent_key)
                if parent_node is None:
                    parent_node = RunGraphNode(
                        id=str(uuid4()),
                        run_id=run_id,
                        attempt_id=attempt_id,
                        node_key=parent_key,
                        node_type="custom",
                        name=parent_key,
                        status="observed",
                        metadata={"source_event_type": "inferred.parent"},
                    )
                    nodes[parent_key] = parent_node
                edges.append(
                    RunGraphEdge(
                        id=str(uuid4()),
                        run_id=run_id,
                        source_node_key=parent_key,
                        target_node_key=node_key,
                        source_node_id=parent_node.id,
                        target_node_id=node.id,
                        edge_type="observed",
                    )
                )
        return RunGraph(
            run_id=run_id,
            attempt_id=attempt_id,
            nodes=list(nodes.values()),
            edges=edges,
        )

    def _node_type(self, event_type: str) -> str:
        if event_type.startswith("model."):
            return "model"
        if event_type.startswith("tool."):
            return "tool"
        if event_type.startswith("retriever."):
            return "retriever"
        if event_type.startswith("ranker."):
            return "ranker"
        if event_type.startswith("generator."):
            return "generator"
        if event_type.startswith("router."):
            return "router"
        if event_type.startswith("human"):
            return "human"
        return "custom"
