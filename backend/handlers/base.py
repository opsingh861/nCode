"""Node handler base Protocol, GenerationContext, and supporting types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import networkx as nx

from backend.core.expression_engine import VariableContext
from backend.core.ir import IRNode
from backend.models.workflow import N8nNode


@dataclass
class GenerationContext:
    """Shared mutable context threaded through all handler invocations.

    Attributes:
        var_context:     Maps n8n node display names to Python variable stems.
        imports:         Accumulated import lines from all handlers.
        packages:        Accumulated pip package names.
        warnings:        Accumulated transpilation warnings.
        mode:            "fastapi" or "script" — chosen before handlers run.
        ai_sub_nodes:    For AI root nodes: dict of connection_type → list of N8nNode
                         that are sub-nodes connected via non-main edges.
        all_node_map:    Full name→node map for the workflow (read-only for handlers).
        dag:             The full workflow DAG (networkx DiGraph). Used by branch handlers
                         to collect sub-graphs for IF/Switch nodes.
        topo_order:      Full topological execution order list. Used by branch handlers
                         to recursively generate IR for branch nodes in the right order.
        processed_nodes: Set of node names already emitted. Branch handlers mark their
                         sub-nodes here so the pipeline loop skips them at the top level.
    """

    var_context: VariableContext = field(default_factory=VariableContext)
    imports: set[str] = field(default_factory=set)
    packages: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
    mode: str = "script"
    ai_sub_nodes: dict[str, list[N8nNode]] = field(default_factory=dict)
    all_node_map: dict[str, N8nNode] = field(default_factory=dict)
    dag: nx.DiGraph = field(default_factory=nx.DiGraph)
    topo_order: list[str] = field(default_factory=list)
    processed_nodes: set[str] = field(default_factory=set)

    def add_import(self, *imports: str) -> None:
        for imp in imports:
            self.imports.add(imp)

    def add_package(self, *packages: str) -> None:
        for pkg in packages:
            self.packages.add(pkg)

    def warn(self, message: str, node_name: str | None = None) -> None:
        prefix = f"[{node_name}] " if node_name else ""
        self.warnings.append(f"{prefix}{message}")

    def register_node_var(self, node_name: str, python_var: str) -> None:
        self.var_context.register(node_name, python_var)

    def resolve_expr(self, value: Any) -> str:
        """Translate a raw n8n parameter value to a Python expression string."""
        from backend.core.expression_engine import translate_expression

        if not isinstance(value, str):
            return repr(value)
        return translate_expression(value, self.var_context)


@runtime_checkable
class NodeHandler(Protocol):
    """Protocol that every node handler must satisfy."""

    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        """Generate an IRNode from an n8n node and current generation context."""
        ...

    def supported_operations(self) -> list[str]:
        """Return list of n8n node type strings this handler supports."""
        ...

    def required_packages(self) -> list[str]:
        """Return pip package names always required by this handler."""
        ...
