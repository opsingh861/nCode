"""Fallback handler for unsupported or unknown n8n node types.

Generates a TODO stub that passes items through unchanged so the overall
workflow structure remains valid Python.
"""

from __future__ import annotations

import re

from backend.core.ir import IRNode, IRNodeKind
from backend.handlers.base import GenerationContext
from backend.handlers.registry import register
from backend.models.workflow import N8nNode


def _safe_var(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_") or "node"
    return f"n_{s}" if s[0].isdigit() else s


@register()  # No types — this is used directly, not via @register lookup.
class FallbackHandler:
    """Generates a pass-through stub for unknown node types."""

    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        code_lines = [
            f"# TODO: Unsupported node type: {node.type!r}",
            f"# Node: {node.name!r}",
            f"{var}_output = {prev_var}  # pass-through stub",
        ]
        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            warnings=[
                f"Unsupported node type: {node.type!r} — generated as pass-through stub"
            ],
        )

    def supported_operations(self) -> list[str]:
        return []

    def required_packages(self) -> list[str]:
        return []


# Module-level singleton for direct use in the pipeline.
FALLBACK = FallbackHandler()
