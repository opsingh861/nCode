"""DAG builder and graph analysis utilities for n8n workflow transpilation.

Uses networkx to:
- Build a directed graph from workflow nodes and connections.
- Compute topological execution order.
- Detect branch/merge points using post-dominator analysis.
- Classify nodes by their structural role.
- Identify AI sub-node clusters (non-main connection types).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    from backend.models.workflow import N8nWorkflow

# Connection types that represent AI sub-node configuration (not execution flow).
AI_CONNECTION_TYPES = frozenset(
    {
        "ai_tool",
        "ai_memory",
        "ai_languageModel",
        "ai_outputParser",
        "ai_retriever",
        "ai_document",
        "ai_embedding",
        "ai_textSplitter",
        "ai_vectorStore",
    }
)

# Node types that act as execution triggers.
TRIGGER_TYPES = frozenset(
    {
        "n8n-nodes-base.manualTrigger",
        "n8n-nodes-base.scheduleTrigger",
        "n8n-nodes-base.webhook",
        "n8n-nodes-base.errorTrigger",
        "n8n-nodes-base.executeWorkflowTrigger",
        "@n8n/n8n-nodes-langchain.chatTrigger",
    }
)

# Node types that produce branching execution (IF / Switch).
BRANCH_TYPES = frozenset(
    {
        "n8n-nodes-base.if",
        "n8n-nodes-base.switch",
    }
)

# Node types that merge multiple execution branches.
MERGE_TYPES = frozenset(
    {
        "n8n-nodes-base.merge",
    }
)


def build_dag(workflow: "N8nWorkflow") -> nx.DiGraph:
    """Build a directed acyclic graph from an N8nWorkflow.

    Each node in the graph corresponds to an n8n node (keyed by display name).
    Node attributes stored:
        - ``type``: n8n node type string
        - ``type_version``: typeVersion field
        - ``parameters``: parameter dict
        - ``disabled``: whether the node is disabled

    Edge attributes stored:
        - ``connection_type``: "main", "ai_tool", "ai_languageModel", etc.
        - ``branch_index``: output branch index (0 = true/first, 1 = false/second...)

    Returns:
        A directed graph. If the workflow contains cycles (invalid for execution),
        they are preserved — callers should detect them via ``has_cycle()``.
    """
    G: nx.DiGraph = nx.DiGraph()

    # Add all nodes first so isolated nodes are still present.
    for node in workflow.nodes:
        G.add_node(
            node.name,
            type=node.type,
            type_version=node.typeVersion,
            parameters=node.parameters,
            disabled=bool(node.disabled),
            node_id=node.id,
        )

    # Add edges from connections.
    for source_name, conn_types in workflow.connections.items():
        for conn_type, outputs in conn_types.items():
            for branch_index, targets in enumerate(outputs):
                for target in targets:
                    if target.node and target.node in G:
                        G.add_edge(
                            source_name,
                            target.node,
                            connection_type=conn_type,
                            branch_index=branch_index,
                        )

    return G


def topological_order(G: nx.DiGraph) -> list[str]:
    """Return node names in topological (dependency-first) execution order.

    Only traverses ``main`` connection edges for execution ordering.
    AI sub-node edges are excluded from the sort — those nodes are handled
    as sub-components of their parent AI root node.

    Raises:
        ValueError: if the main-flow subgraph contains a cycle.
    """
    # Build subgraph with only main-flow edges.
    main_edges = [
        (u, v)
        for u, v, data in G.edges(data=True)
        if data.get("connection_type", "main") == "main"
    ]
    main_G: nx.DiGraph = nx.DiGraph()
    main_G.add_nodes_from(G.nodes())
    main_G.add_edges_from(main_edges)

    try:
        return list(nx.topological_sort(main_G))
    except nx.NetworkXUnfeasible as exc:
        raise ValueError(
            "Workflow contains a cycle in the main execution flow — cannot transpile."
        ) from exc


def find_merge_point(G: nx.DiGraph, branch_node_name: str) -> str | None:
    """Find the post-dominator merge point for a branch node.

    Uses reversed-graph immediate dominators (post-dominator tree analysis).
    The merge point is the first common descendant that all branch outputs
    eventually reach — i.e., the immediate post-dominator of the branch.

    Args:
        G:                The full workflow DAG.
        branch_node_name: Name of the IF or Switch node.

    Returns:
        Name of the merge point node, or None if no merge point exists.
    """
    # Work only on main-flow edges.
    main_edges = [
        (u, v)
        for u, v, data in G.edges(data=True)
        if data.get("connection_type", "main") == "main"
    ]
    main_G: nx.DiGraph = nx.DiGraph()
    main_G.add_nodes_from(G.nodes())
    main_G.add_edges_from(main_edges)

    # Find direct successors (branch targets).
    successors = list(main_G.successors(branch_node_name))
    if len(successors) < 2:
        return None

    # Collect all nodes reachable from each branch output.
    reachable_sets = [
        nx.descendants(main_G, succ) | {succ} for succ in successors
    ]

    # The merge point candidates are nodes reachable from ALL branches.
    common_descendants = reachable_sets[0].intersection(*reachable_sets[1:])
    if not common_descendants:
        return None

    # Among common descendants, the merge point is the topologically earliest one.
    try:
        topo = list(nx.topological_sort(main_G))
    except nx.NetworkXUnfeasible:
        return None

    for node in topo:
        if node in common_descendants:
            return node

    return None


def get_branch_subgraph(
    G: nx.DiGraph, start: str, merge_point: str | None
) -> list[str]:
    """Collect all nodes belonging to a single branch between start and merge_point.

    Args:
        G:           The full workflow DAG.
        start:       The first node of this branch (direct successor of the IF/Switch).
        merge_point: The node where branches converge, or None.

    Returns:
        Ordered list of node names in this branch (topological order),
        not including the merge_point itself.
    """
    main_edges = [
        (u, v)
        for u, v, data in G.edges(data=True)
        if data.get("connection_type", "main") == "main"
    ]
    main_G: nx.DiGraph = nx.DiGraph()
    main_G.add_nodes_from(G.nodes())
    main_G.add_edges_from(main_edges)

    # Collect all nodes reachable from start, stopping at merge_point.
    visited: set[str] = set()
    queue = [start]
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        if merge_point and node == merge_point:
            continue
        visited.add(node)
        for succ in main_G.successors(node):
            if succ not in visited:
                queue.append(succ)

    # Return in topological order.
    try:
        topo = list(nx.topological_sort(main_G))
    except nx.NetworkXUnfeasible:
        return list(visited)

    return [n for n in topo if n in visited]


def classify_node(G: nx.DiGraph, node_name: str) -> str:
    """Classify a node's structural role in the execution graph.

    Returns one of: "trigger", "branch", "merge", "ai_sub", "regular".
    """
    node_data = G.nodes.get(node_name, {})
    node_type = node_data.get("type", "").lower()

    # Check against known type sets (case-insensitive base type).
    for known_type in TRIGGER_TYPES:
        if known_type.lower() == node_type:
            return "trigger"

    for known_type in BRANCH_TYPES:
        if known_type.lower() == node_type:
            return "branch"

    for known_type in MERGE_TYPES:
        if known_type.lower() == node_type:
            return "merge"

    # Check if this node is only reachable via non-main edges (AI sub-node).
    incoming_edges = list(G.in_edges(node_name, data=True))
    if incoming_edges and all(
        data.get("connection_type", "main") in AI_CONNECTION_TYPES
        for _, _, data in incoming_edges
    ):
        return "ai_sub"

    return "regular"


def get_ai_sub_nodes(G: nx.DiGraph, ai_root_name: str) -> dict[str, list[str]]:
    """Return AI sub-nodes grouped by connection type for an AI root node.

    Args:
        G:            The full workflow DAG.
        ai_root_name: Name of the AI root node (Agent, LLM Chain, etc.)

    Returns:
        Dict mapping connection_type -> list of node names connected via that type.
        Example: {"ai_languageModel": ["OpenAI Chat Model"], "ai_memory": ["Buffer Memory"]}
    """
    result: dict[str, list[str]] = {}
    for pred, _, data in G.in_edges(ai_root_name, data=True):
        conn_type = data.get("connection_type", "main")
        if conn_type in AI_CONNECTION_TYPES:
            result.setdefault(conn_type, []).append(pred)
    return result


def get_merge_input_vars(
    G: nx.DiGraph,
    merge_node_name: str,
    var_context: "Any",
) -> list[str]:
    """Return Python output variable names for all main-flow predecessors of a merge node.

    Args:
        G:                The full workflow DAG.
        merge_node_name:  Name of the Merge node.
        var_context:      A VariableContext instance with registered node→var mappings.

    Returns:
        List of Python variable names (e.g. ``["true_path_output", "false_path_output"]``).
        Returns an empty list if no predecessors are found.
    """
    predecessors = [
        u
        for u, _, data in G.in_edges(merge_node_name, data=True)
        if data.get("connection_type", "main") == "main"
    ]
    return [var_context.resolve(pred) for pred in predecessors]


def has_cycle(G: nx.DiGraph) -> bool:
    """Return True if the main execution flow contains a cycle."""
    main_edges = [
        (u, v)
        for u, v, data in G.edges(data=True)
        if data.get("connection_type", "main") == "main"
    ]
    main_G: nx.DiGraph = nx.DiGraph()
    main_G.add_nodes_from(G.nodes())
    main_G.add_edges_from(main_edges)
    return not nx.is_directed_acyclic_graph(main_G)
