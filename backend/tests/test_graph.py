"""Tests for the DAG builder and graph analysis (backend/core/graph.py)."""

import networkx as nx
import pytest
from backend.core.graph import (
    build_dag,
    classify_node,
    find_merge_point,
    get_ai_sub_nodes,
    get_branch_subgraph,
    has_cycle,
    topological_order,
)
from backend.models.workflow import N8nWorkflow

# ---------------------------------------------------------------------------
# Workflow fixture helpers
# ---------------------------------------------------------------------------


def _make_node(name: str, node_type: str = "n8n-nodes-base.set", **extra) -> dict:
    return {
        "id": name.replace(" ", "_").lower(),
        "name": name,
        "type": node_type,
        "typeVersion": 1,
        "position": [0, 0],
        "parameters": extra.get("parameters", {}),
    }


def _make_workflow(nodes: list[dict], connections: dict) -> N8nWorkflow:
    return N8nWorkflow.model_validate(
        {
            "name": "Test Workflow",
            "nodes": nodes,
            "connections": connections,
        }
    )


def _linear_conn(source: str, target: str) -> dict:
    """Helper: source → target via main[0]."""
    return {source: {"main": [[{"node": target, "type": "main", "index": 0}]]}}


def _merge_connections(*conns: dict) -> dict:
    result: dict = {}
    for c in conns:
        for source, targets in c.items():
            if source not in result:
                result[source] = {"main": []}
            existing = result[source]["main"]
            for branch_list in targets.get("main", []):
                existing.append(branch_list)
    return result


# ---------------------------------------------------------------------------
# build_dag
# ---------------------------------------------------------------------------


class TestBuildDag:
    def test_linear_graph(self):
        wf = _make_workflow(
            [_make_node("A"), _make_node("B")],
            {"A": {"main": [[{"node": "B", "type": "main", "index": 0}]]}},
        )
        G = build_dag(wf)
        assert "A" in G
        assert "B" in G
        assert G.has_edge("A", "B")

    def test_node_attributes(self):
        wf = _make_workflow(
            [_make_node("A", "n8n-nodes-base.httpRequest")],
            {},
        )
        G = build_dag(wf)
        assert G.nodes["A"]["type"] == "n8n-nodes-base.httpRequest"

    def test_isolated_node_included(self):
        wf = _make_workflow(
            [_make_node("Isolated"), _make_node("Other")],
            {},
        )
        G = build_dag(wf)
        assert "Isolated" in G
        assert "Other" in G

    def test_edge_connection_type(self):
        wf = _make_workflow(
            [_make_node("LLM"), _make_node("Agent")],
            {
                "LLM": {
                    "ai_languageModel": [
                        [{"node": "Agent", "type": "ai_languageModel", "index": 0}]
                    ]
                }
            },
        )
        G = build_dag(wf)
        edge_data = G.edges["LLM", "Agent"]
        assert edge_data["connection_type"] == "ai_languageModel"


# ---------------------------------------------------------------------------
# topological_order
# ---------------------------------------------------------------------------


class TestTopologicalOrder:
    def test_linear_order(self):
        wf = _make_workflow(
            [_make_node("A"), _make_node("B"), _make_node("C")],
            {
                "A": {"main": [[{"node": "B", "type": "main", "index": 0}]]},
                "B": {"main": [[{"node": "C", "type": "main", "index": 0}]]},
            },
        )
        G = build_dag(wf)
        order = topological_order(G)
        assert order.index("A") < order.index("B") < order.index("C")

    def test_single_node(self):
        wf = _make_workflow([_make_node("Solo")], {})
        G = build_dag(wf)
        order = topological_order(G)
        assert "Solo" in order

    def test_raises_on_cycle(self):
        wf = _make_workflow(
            [_make_node("A"), _make_node("B")],
            {
                "A": {"main": [[{"node": "B", "type": "main", "index": 0}]]},
                "B": {"main": [[{"node": "A", "type": "main", "index": 0}]]},
            },
        )
        G = build_dag(wf)
        with pytest.raises(ValueError, match="cycle"):
            topological_order(G)


# ---------------------------------------------------------------------------
# find_merge_point
# ---------------------------------------------------------------------------


class TestFindMergePoint:
    def _diamond_workflow(self) -> tuple[N8nWorkflow, nx.DiGraph]:
        """IF → [TrueA, FalseB] → Merge"""
        wf = _make_workflow(
            [
                _make_node("Trigger"),
                _make_node("IF", "n8n-nodes-base.if"),
                _make_node("TrueA"),
                _make_node("FalseB"),
                _make_node("Merge", "n8n-nodes-base.merge"),
            ],
            {
                "Trigger": {"main": [[{"node": "IF", "type": "main", "index": 0}]]},
                "IF": {
                    "main": [
                        [{"node": "TrueA", "type": "main", "index": 0}],
                        [{"node": "FalseB", "type": "main", "index": 0}],
                    ]
                },
                "TrueA": {"main": [[{"node": "Merge", "type": "main", "index": 0}]]},
                "FalseB": {"main": [[{"node": "Merge", "type": "main", "index": 0}]]},
            },
        )
        return wf, build_dag(wf)

    def test_finds_merge_in_diamond(self):
        wf, G = self._diamond_workflow()
        merge = find_merge_point(G, "IF")
        assert merge == "Merge"

    def test_no_merge_for_linear(self):
        wf = _make_workflow(
            [_make_node("A"), _make_node("B")],
            {"A": {"main": [[{"node": "B", "type": "main", "index": 0}]]}},
        )
        G = build_dag(wf)
        assert find_merge_point(G, "A") is None


# ---------------------------------------------------------------------------
# get_branch_subgraph
# ---------------------------------------------------------------------------


class TestGetBranchSubgraph:
    def test_true_branch_nodes(self):
        wf = _make_workflow(
            [
                _make_node("IF", "n8n-nodes-base.if"),
                _make_node("TrueA"),
                _make_node("TrueB"),
                _make_node("Merge"),
            ],
            {
                "IF": {
                    "main": [
                        [{"node": "TrueA", "type": "main", "index": 0}],
                    ]
                },
                "TrueA": {"main": [[{"node": "TrueB", "type": "main", "index": 0}]]},
                "TrueB": {"main": [[{"node": "Merge", "type": "main", "index": 0}]]},
            },
        )
        G = build_dag(wf)
        branch = get_branch_subgraph(G, "TrueA", "Merge")
        assert "TrueA" in branch
        assert "TrueB" in branch
        assert "Merge" not in branch


# ---------------------------------------------------------------------------
# classify_node
# ---------------------------------------------------------------------------


class TestClassifyNode:
    def test_trigger_classification(self):
        wf = _make_workflow(
            [_make_node("T", "n8n-nodes-base.manualTrigger")],
            {},
        )
        G = build_dag(wf)
        assert classify_node(G, "T") == "trigger"

    def test_branch_classification(self):
        wf = _make_workflow(
            [
                _make_node("IF", "n8n-nodes-base.if"),
                _make_node("A"),
                _make_node("B"),
            ],
            {
                "IF": {
                    "main": [
                        [{"node": "A", "type": "main", "index": 0}],
                        [{"node": "B", "type": "main", "index": 0}],
                    ]
                },
            },
        )
        G = build_dag(wf)
        assert classify_node(G, "IF") == "branch"

    def test_regular_classification(self):
        wf = _make_workflow(
            [_make_node("Set", "n8n-nodes-base.set")],
            {},
        )
        G = build_dag(wf)
        assert classify_node(G, "Set") == "regular"


# ---------------------------------------------------------------------------
# get_ai_sub_nodes
# ---------------------------------------------------------------------------


class TestGetAiSubNodes:
    def test_llm_sub_node(self):
        wf = _make_workflow(
            [
                _make_node("GPT4", "@n8n/n8n-nodes-langchain.lmChatOpenAi"),
                _make_node("Agent", "@n8n/n8n-nodes-langchain.agent"),
            ],
            {
                "GPT4": {
                    "ai_languageModel": [
                        [{"node": "Agent", "type": "ai_languageModel", "index": 0}]
                    ]
                },
            },
        )
        G = build_dag(wf)
        subs = get_ai_sub_nodes(G, "Agent")
        assert "ai_languageModel" in subs
        assert "GPT4" in subs["ai_languageModel"]

    def test_no_subs(self):
        wf = _make_workflow([_make_node("Set")], {})
        G = build_dag(wf)
        assert get_ai_sub_nodes(G, "Set") == {}


# ---------------------------------------------------------------------------
# has_cycle
# ---------------------------------------------------------------------------


class TestHasCycle:
    def test_no_cycle(self):
        wf = _make_workflow(
            [_make_node("A"), _make_node("B")],
            {"A": {"main": [[{"node": "B", "type": "main", "index": 0}]]}},
        )
        G = build_dag(wf)
        assert not has_cycle(G)

    def test_detects_cycle(self):
        wf = _make_workflow(
            [_make_node("A"), _make_node("B")],
            {
                "A": {"main": [[{"node": "B", "type": "main", "index": 0}]]},
                "B": {"main": [[{"node": "A", "type": "main", "index": 0}]]},
            },
        )
        G = build_dag(wf)
        assert has_cycle(G)
