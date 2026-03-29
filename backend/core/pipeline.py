"""Pipeline orchestrator.

`run_pipeline` is the single public entry point used by the FastAPI router.
It accepts raw JSON (string or dict), walks the workflow through all phases,
and returns a `PipelineResult`.

Pipeline phases
---------------
1. Parse      — validate raw JSON into an N8nWorkflow via Pydantic.
2. Build DAG  — construct networkx DiGraph with build_dag().
3. Topo sort  — determine execution order (main-flow only).
4. Mode       — detect "fastapi" vs "script" from trigger node types.
5. Emit IR    — for each node in topo order, call the appropriate handler
               and collect IRNode objects into an IRProgram.
6. Emit code  — emit_program(ir_program) → raw Python source string.
7. Format     — post_process(source) → black+isort formatted source.
8. Return     — bundle result into PipelineResult.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import backend.handlers  # noqa: F401 — triggers all @register side-effects via __init__.py
from backend.core.emitter import emit_program
from backend.core.expression_engine import VariableContext
from backend.core.graph import (
    AI_CONNECTION_TYPES,
    build_dag,
    classify_node,
    find_merge_point,
    get_ai_sub_nodes,
    get_branch_subgraph,
    get_merge_input_vars,
    topological_order,
)
from backend.core.ir import IRNode, IRNodeKind, IRProgram
from backend.core.post_processor import post_process
from backend.handlers import _ensure_all_registered  # noqa: F401
from backend.handlers.base import GenerationContext
from backend.handlers.fallback import FALLBACK
from backend.handlers.registry import get_handler
from backend.handlers.triggers import is_fastapi_trigger
from backend.models.workflow import N8nWorkflow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    workflow_name: str
    generated_code: str
    requirements_txt: str
    warnings: list[str]
    download_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dag_node_count: int = 0
    dag_edge_count: int = 0
    mode: str = "script"
    supported_nodes: list[str] = field(default_factory=list)
    unsupported_nodes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_pipeline(raw: str | dict[str, Any]) -> PipelineResult:
    """Full transpilation pipeline.  Returns a PipelineResult."""
    # ── Phase 1: Parse ──────────────────────────────────────────────────────
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc
    else:
        data = raw

    workflow = N8nWorkflow.model_validate(data)

    # ── Phase 2: Build DAG ──────────────────────────────────────────────────
    G = build_dag(workflow)
    dag_node_count = G.number_of_nodes()
    dag_edge_count = G.number_of_edges()

    # ── Phase 3: Topological order ──────────────────────────────────────────
    try:
        topo = topological_order(G)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    # ── Phase 4: Mode detection ─────────────────────────────────────────────
    mode = _detect_mode(workflow)

    # ── Phase 5: Emit IR ────────────────────────────────────────────────────
    ctx = GenerationContext(
        var_context=VariableContext(),
        mode=mode,
        all_node_map={n.name: n for n in workflow.nodes},
        dag=G,
        topo_order=topo,
    )

    node_map = {n.name: n for n in workflow.nodes}
    ir_nodes: list[IRNode] = []
    visited: set[str] = ctx.processed_nodes  # share the same set

    supported_nodes: list[str] = []
    unsupported_nodes: list[str] = []

    for node_name in topo:
        if node_name in visited:
            continue
        if node_name not in node_map:
            continue

        n8n_node = node_map[node_name]
        node_type_lower = n8n_node.type.lower()

        # Skip disabled nodes
        if n8n_node.disabled:
            visited.add(node_name)
            continue

        # ── AI sub-nodes: handled by their root AI node; skip standalone ──
        # We detect if this node is an AI sub-node by checking out-edges:
        # sub-nodes (tools, memory, LLM models) are source nodes whose
        # ALL out-edges target an AI root via non-main connection types.
        out_edges = list(G.out_edges(node_name, data=True))
        if out_edges and all(
            e[2].get("connection_type", "main") in AI_CONNECTION_TYPES
            for e in out_edges
        ):
            visited.add(node_name)
            continue

        # ── Populate ai_sub_nodes for this node (if it is an AI root) ─────
        ai_subs = get_ai_sub_nodes(G, node_name)
        ctx.ai_sub_nodes = {
            conn_type: [node_map[n] for n in names if n in node_map]
            for conn_type, names in ai_subs.items()
        }

        # ── Get handler ───────────────────────────────────────────────────
        handler = get_handler(n8n_node.type)
        if handler is None:
            handler = FALLBACK
            unsupported_nodes.append(n8n_node.type)
            ctx.warn(
                f"No handler for node type {n8n_node.type!r} — using pass-through stub",
                node_name,
            )
        else:
            supported_nodes.append(n8n_node.type)

        # ── Generate IR ───────────────────────────────────────────────────
        try:
            ir_node = handler.generate(n8n_node, ctx)
        except Exception as exc:
            logger.exception("Handler %r failed on node %r", n8n_node.type, node_name)
            ir_node = IRNode(
                node_id=n8n_node.id,
                node_name=node_name,
                kind=IRNodeKind.STATEMENT,
                python_var=_safe_var(node_name),
                code_lines=[
                    f"# ERROR generating node {node_name!r}: {exc}",
                    f"# Falling back to pass-through",
                    f"{_safe_var(node_name)}_output = {{}}",
                ],
                warnings=[str(exc)],
            )
            ctx.warn(f"Handler raised exception: {exc}", node_name)

        # Accumulate imports/packages from ir_node into ctx
        for imp in ir_node.imports:
            ctx.add_import(imp)
        for pkg in ir_node.pip_packages:
            ctx.add_package(pkg)

        ir_nodes.append(ir_node)
        visited.add(node_name)

    # ── Assemble IRProgram ─────────────────────────────────────────────────
    all_imports = set(ctx.imports)
    # Ensure FastAPI imports are present when in fastapi mode
    if mode == "fastapi":
        all_imports.add("from fastapi import FastAPI")
        all_imports.add("import uvicorn")

    ir_program = IRProgram(
        workflow_name=workflow.name,
        nodes=ir_nodes,
        all_imports=all_imports,
        all_packages=set(ctx.packages),
        mode=mode,
        warnings=ctx.warnings[:],
        trigger_info=_collect_trigger_info(workflow),
    )

    # ── Phase 6: Emit code ─────────────────────────────────────────────────
    raw_source = emit_program(ir_program)

    # ── Phase 7: Format ────────────────────────────────────────────────────
    formatted_source, fmt_warnings = post_process(raw_source)
    ir_program.warnings.extend(fmt_warnings)

    # ── Phase 8: Build requirements.txt ───────────────────────────────────
    requirements = _build_requirements(ir_program.all_packages)

    return PipelineResult(
        workflow_name=workflow.name,
        generated_code=formatted_source,
        requirements_txt=requirements,
        warnings=ir_program.warnings,
        dag_node_count=dag_node_count,
        dag_edge_count=dag_edge_count,
        mode=mode,
        supported_nodes=supported_nodes,
        unsupported_nodes=unsupported_nodes,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FASTAPI_TRIGGER_TYPES = frozenset(
    {
        "n8n-nodes-base.webhook",
        "@n8n/n8n-nodes-langchain.chattrigger",
        "@n8n/n8n-nodes-langchain.chatTrigger",
    }
)


def _detect_mode(workflow: N8nWorkflow) -> str:
    """Return "fastapi" if the workflow starts with a webhook/chat trigger, else "script"."""
    for node in workflow.nodes:
        if is_fastapi_trigger(node.type):
            return "fastapi"
    return "script"


def _collect_trigger_info(workflow: N8nWorkflow) -> dict:
    info: dict = {}
    for node in workflow.nodes:
        t = node.type.lower()
        if "trigger" in t or "webhook" in t:
            info[node.name] = {
                "type": node.type,
                "parameters": node.parameters,
            }
    return info


def _build_requirements(packages: set[str]) -> str:
    if not packages:
        return ""
    return "\n".join(sorted(packages, key=str.lower)) + "\n"


def _safe_var(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_") or "node"
    return f"n_{s}" if s[0].isdigit() else s
