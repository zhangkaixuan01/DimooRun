from dimoo_run.core.events import AgentEvent
from dimoo_run.run_graph.projector import RunGraphProjector


def test_run_graph_projector_maps_events_to_observation_nodes() -> None:
    projector = RunGraphProjector()

    graph = projector.project(
        run_id=1,
        attempt_id="attempt_1",
        events=[
            AgentEvent(
                type="model.started",
                payload={"node_key": "llm", "name": "Generate", "input_ref": "artifact://in"},
                sequence=1,
            ),
            AgentEvent(
                type="model.completed",
                payload={"node_key": "llm", "output_ref": "artifact://out", "latency_ms": 120},
                sequence=2,
            ),
            AgentEvent(
                type="tool.called",
                payload={"node_key": "search", "name": "Search"},
                sequence=3,
            ),
            AgentEvent(
                type="tool.completed",
                payload={"node_key": "search", "parent_node_key": "llm"},
                sequence=4,
            ),
        ],
    )

    assert [node.node_type for node in graph.nodes] == ["model", "tool"]
    assert graph.nodes[0].status == "succeeded"
    assert graph.nodes[0].input_ref == "artifact://in"
    assert graph.nodes[0].output_ref == "artifact://out"
    assert graph.nodes[0].latency_ms == 120
    assert graph.edges[0].source_node_key == "llm"
    assert graph.edges[0].target_node_key == "search"
    assert graph.edges[0].source_node_id == graph.nodes[0].id
    assert graph.edges[0].target_node_id == graph.nodes[1].id


def test_run_graph_projector_degrades_unknown_events_to_custom_nodes() -> None:
    graph = RunGraphProjector().project(
        run_id=1,
        attempt_id="attempt_1",
        events=[
            AgentEvent(
                type="framework.custom.step",
                payload={"node_key": "custom-1", "name": "Custom Step"},
                sequence=1,
            )
        ],
    )

    assert graph.nodes[0].node_type == "custom"
    assert graph.nodes[0].status == "succeeded"


def test_run_graph_projector_creates_placeholder_parent_for_out_of_order_edges() -> None:
    graph = RunGraphProjector().project(
        run_id=1,
        attempt_id="attempt_1",
        events=[
            AgentEvent(
                type="tool.completed",
                payload={"node_key": "search", "parent_node_key": "llm"},
                sequence=1,
            )
        ],
    )

    nodes_by_key = {node.node_key: node for node in graph.nodes}
    assert {"llm", "search"} <= set(nodes_by_key)
    assert graph.edges[0].source_node_id == nodes_by_key["llm"].id
    assert graph.edges[0].target_node_id == nodes_by_key["search"].id
# mypy: disable-error-code="arg-type"
