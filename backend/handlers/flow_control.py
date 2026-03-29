"""Flow control node handlers: IF, Switch, Merge, Split In Batches, Wait, Respond to Webhook."""

from __future__ import annotations

import re
from typing import Any

import networkx as nx

from backend.core.ir import IRNode, IRNodeKind
from backend.handlers.base import GenerationContext
from backend.handlers.registry import register
from backend.models.workflow import N8nNode


def _safe_var(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_") or "node"
    return f"n_{s}" if s[0].isdigit() else s


def _generate_branch_nodes(
    branch_nodes: list[str],
    ctx: GenerationContext,
) -> list[IRNode]:
    """Recursively generate IRNodes for all nodes in a branch.

    This reuses the same GenerationContext so variable registrations persist.
    Each node name in *branch_nodes* is marked as processed in ctx.processed_nodes
    so the top-level pipeline loop skips them.
    """
    from backend.core.graph import AI_CONNECTION_TYPES, get_ai_sub_nodes
    from backend.handlers.fallback import FALLBACK
    from backend.handlers.registry import get_handler

    ir_nodes: list[IRNode] = []
    node_map = ctx.all_node_map
    G = ctx.dag

    for node_name in branch_nodes:
        if node_name in ctx.processed_nodes:
            continue
        if node_name not in node_map:
            continue

        n8n_node = node_map[node_name]
        if n8n_node.disabled:
            ctx.processed_nodes.add(node_name)
            continue

        # Skip AI sub-nodes
        out_edges = list(G.out_edges(node_name, data=True))
        if out_edges and all(
            e[2].get("connection_type", "main") in AI_CONNECTION_TYPES
            for e in out_edges
        ):
            ctx.processed_nodes.add(node_name)
            continue

        # Populate ai_sub_nodes for this node if applicable
        ai_subs = get_ai_sub_nodes(G, node_name)
        ctx.ai_sub_nodes = {
            conn_type: [node_map[n] for n in names if n in node_map]
            for conn_type, names in ai_subs.items()
        }

        handler = get_handler(n8n_node.type)
        if handler is None:
            handler = FALLBACK

        try:
            ir_node = handler.generate(n8n_node, ctx)
        except Exception as exc:
            var = _safe_var(node_name)
            ir_node = IRNode(
                node_id=n8n_node.id,
                node_name=node_name,
                kind=IRNodeKind.STATEMENT,
                python_var=var,
                code_lines=[
                    f"# ERROR generating node {node_name!r}: {exc}",
                    f"{var}_output = {{}}",
                ],
                warnings=[str(exc)],
            )

        for imp in ir_node.imports:
            ctx.add_import(imp)
        for pkg in ir_node.pip_packages:
            ctx.add_package(pkg)

        ir_nodes.append(ir_node)
        ctx.processed_nodes.add(node_name)

    return ir_nodes


# ---------------------------------------------------------------------------
# Condition translation helpers
# ---------------------------------------------------------------------------


def _translate_condition_v1(condition: dict, ctx: GenerationContext) -> str:
    """Translate a v1-style condition dict to a Python boolean expression."""
    value1 = ctx.resolve_expr(str(condition.get("value1", "")))
    value2 = ctx.resolve_expr(str(condition.get("value2", "")))
    op_type = str(condition.get("operation", "equal")).lower()

    op_map = {
        "equal": f"{value1} == {value2}",
        "notequal": f"{value1} != {value2}",
        "largerthan": f"{value1} > {value2}",
        "largerthanorequalto": f"{value1} >= {value2}",
        "smallerthan": f"{value1} < {value2}",
        "smallerthanorequalto": f"{value1} <= {value2}",
        "contains": f"{value2} in {value1}",
        "notcontains": f"{value2} not in {value1}",
        "startswith": f"str({value1}).startswith(str({value2}))",
        "endswith": f"str({value1}).endswith(str({value2}))",
        "regex": f"bool(re.search({value2}, str({value1})))",
        "isempty": f"not {value1}",
        "isnotempty": f"bool({value1})",
        "exists": f"{value1} is not None",
        "notexists": f"{value1} is None",
    }
    return op_map.get(op_type, f"{value1} == {value2}")


def _translate_condition_v2(condition: dict, ctx: GenerationContext) -> str:
    """Translate a v2-style condition (operator object) to Python."""
    left = ctx.resolve_expr(str(condition.get("leftValue", "")))
    right = ctx.resolve_expr(str(condition.get("rightValue", "")))

    operator_obj = condition.get("operator", {})
    op = str(operator_obj.get("operation", "equals")).lower()
    op_type = str(operator_obj.get("type", "string")).lower()

    if op_type == "boolean":
        if op in ("true", "equals") and right in ("True", "repr(True)"):
            return f"bool({left})"
        if op == "false":
            return f"not bool({left})"

    op_map = {
        "equals": f"{left} == {right}",
        "notequals": f"{left} != {right}",
        "larger": f"{left} > {right}",
        "largerequal": f"{left} >= {right}",
        "smaller": f"{left} < {right}",
        "smallerequal": f"{left} <= {right}",
        "contains": f"{right} in str({left})",
        "notcontains": f"{right} not in str({left})",
        "startswith": f"str({left}).startswith(str({right}))",
        "endswith": f"str({left}).endswith(str({right}))",
        "regex": f"bool(re.search({right}, str({left})))",
        "isempty": f"not {left}",
        "isnotempty": f"bool({left})",
        "exists": f"{left} is not None",
        "notexists": f"{left} is None",
        "true": f"bool({left})",
        "false": f"not bool({left})",
    }
    return op_map.get(op, f"{left} == {right}")


def _conditions_to_python(conditions_spec: Any, ctx: GenerationContext) -> str:
    """Convert an IF node conditions spec to a Python boolean expression."""
    if not conditions_spec:
        return "True"

    # v2 style: {"conditions": [...], "combinator": "and"/"or"}
    if isinstance(conditions_spec, dict) and "conditions" in conditions_spec:
        combinator = str(conditions_spec.get("combinator", "and")).lower()
        conditions = conditions_spec.get("conditions", [])
        python_op = " and " if combinator == "and" else " or "
        parts = [
            _translate_condition_v2(c, ctx) for c in conditions if isinstance(c, dict)
        ]
        if not parts:
            return "True"
        return f"({python_op.join(parts)})"

    # v1 style: a flat list of conditions with a top-level combinator
    if isinstance(conditions_spec, dict):
        combinator = str(conditions_spec.get("combineOperation", "all")).lower()
        python_op = " and " if combinator == "all" else " or "
        conds = []
        for key in ("string", "number", "boolean", "dateTime"):
            for c in conditions_spec.get(key, []):
                if isinstance(c, dict):
                    conds.append(_translate_condition_v1(c, ctx))
        if not conds:
            return "True"
        return f"({python_op.join(conds)})"

    if isinstance(conditions_spec, list):
        parts = [
            _translate_condition_v1(c, ctx)
            for c in conditions_spec
            if isinstance(c, dict)
        ]
        return f"({' and '.join(parts)})" if parts else "True"

    return "True"


# ---------------------------------------------------------------------------
# IF Node
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.if")
class IfNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        # Capture prev_var BEFORE registering this node so conditions reference
        # the previous node's output, not the IF node itself.
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        ctx.processed_nodes.add(node.name)
        params = node.parameters

        conditions_spec = params.get("conditions", params.get("condition", {}))
        condition_expr = _conditions_to_python(conditions_spec, ctx)

        # The condition line.  Emitter knows to add if/else blocks with branch nodes.
        code_lines = [f"if {condition_expr}:"]

        # Determine branch node sets using the DAG (if available)
        true_ir_nodes: list[IRNode] = []
        false_ir_nodes: list[IRNode] = []

        G = ctx.dag
        if G.number_of_nodes() > 0:
            from backend.core.graph import find_merge_point, get_branch_subgraph

            merge_point = find_merge_point(G, node.name)
            successors = [
                (v, data.get("branch_index", 0))
                for _, v, data in G.out_edges(node.name, data=True)
                if data.get("connection_type", "main") == "main"
            ]
            # Sort by branch_index: 0 = true branch, 1 = false branch
            successors.sort(key=lambda x: x[1])

            if len(successors) >= 1:
                true_start = successors[0][0]
                true_nodes = get_branch_subgraph(G, true_start, merge_point)
                true_ir_nodes = _generate_branch_nodes(true_nodes, ctx)

            if len(successors) >= 2:
                false_start = successors[1][0]
                false_nodes = get_branch_subgraph(G, false_start, merge_point)
                false_ir_nodes = _generate_branch_nodes(false_nodes, ctx)

        # Prepend preamble IRNodes to each branch so the emitter can emit them.
        # The preamble sets the true/false output variables at the start of each branch.
        preamble_true = IRNode(
            node_id=f"{node.id}__true_pre",
            node_name=f"{node.name}__true_pre",
            kind=IRNodeKind.STATEMENT,
            python_var=f"{var}_pre",
            code_lines=[f"{var}_true_output = {prev_var}", f"{var}_false_output = []"],
        )
        preamble_false = IRNode(
            node_id=f"{node.id}__false_pre",
            node_name=f"{node.name}__false_pre",
            kind=IRNodeKind.STATEMENT,
            python_var=f"{var}_pre",
            code_lines=[f"{var}_true_output = []", f"{var}_false_output = {prev_var}"],
        )

        ir_node = IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.IF_BRANCH,
            python_var=var,
            imports=["import re"],
            code_lines=code_lines,
            comment=f"IF condition: {condition_expr[:60]}{'...' if len(condition_expr) > 60 else ''}",
        )
        # true_branch / false_branch lists are processed by the emitter.
        # Preamble nodes are prepended so they run first inside each branch.
        ir_node.branches["true_branch"] = [preamble_true] + true_ir_nodes
        ir_node.branches["false_branch"] = [preamble_false] + false_ir_nodes
        # Epilogue: the unified output variable (emitter appends this after the else block)
        ir_node.branches["_epilogue_lines"] = [  # type: ignore[assignment]
            IRNode(
                node_id=f"{node.id}__epilogue",
                node_name=f"{node.name}__epilogue",
                kind=IRNodeKind.STATEMENT,
                python_var=f"{var}_epi",
                code_lines=[
                    f"{var}_output = {var}_true_output if {var}_true_output else {var}_false_output"
                ],
            )
        ]
        return ir_node

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.if"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Switch Node
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.switch")
class SwitchNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        # Capture prev_var BEFORE registering so it refers to the previous output
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        ctx.processed_nodes.add(node.name)
        params = node.parameters

        mode = str(params.get("mode", "rules")).lower()

        code_lines: list[str] = []

        if mode == "expression":
            val_expr = ctx.resolve_expr(str(params.get("value", "")))
            code_lines += [
                f"{var}_switch_val = {val_expr}",
                f"# Switch on expression value — add your output routing below",
                f"{var}_output = {prev_var}",
            ]
        else:
            # Rules mode
            rules = params.get("rules", {})
            rule_list = rules.get("rules", []) if isinstance(rules, dict) else []

            for i, rule in enumerate(rule_list):
                if not isinstance(rule, dict):
                    continue
                cond = _translate_condition_v1(rule, ctx)
                if i == 0:
                    code_lines.append(f"if {cond}:")
                    code_lines.append(f"    {var}_output_{i} = {prev_var}")
                else:
                    code_lines.append(f"elif {cond}:")
                    code_lines.append(f"    {var}_output_{i} = {prev_var}")

            # Fallback output
            fallback_output = params.get("fallbackOutput", -1)
            if fallback_output == -1 or str(fallback_output) == "none":
                code_lines.append(f"else:")
                code_lines.append(f"    {var}_output_fallback = []")
            else:
                code_lines.append(f"else:")
                code_lines.append(f"    {var}_output_fallback = {prev_var}")

            # Unified output is first match or fallback
            n_rules = len(rule_list)
            if n_rules > 0:
                code_lines.append(
                    f"{var}_output = {var}_output_0 if '{var}_output_0' in dir() else {var}_output_fallback if '{var}_output_fallback' in dir() else []"
                )
            else:
                code_lines.append(f"{var}_output = {prev_var}")

        # Collect branch IR nodes from DAG and embed them inside the switch structure.
        branch_ir: dict[str, list[IRNode]] = {}
        G = ctx.dag
        if G.number_of_nodes() > 0:
            from backend.core.graph import find_merge_point, get_branch_subgraph

            merge_point = find_merge_point(G, node.name)
            successors = [
                (v, data.get("branch_index", 0))
                for _, v, data in G.out_edges(node.name, data=True)
                if data.get("connection_type", "main") == "main"
            ]
            successors.sort(key=lambda x: x[1])
            for branch_start, branch_idx in successors:
                branch_nodes = get_branch_subgraph(G, branch_start, merge_point)
                branch_key = f"branch_{branch_idx}"
                branch_ir[branch_key] = _generate_branch_nodes(branch_nodes, ctx)

        ir_node = IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.SWITCH_BRANCH,
            python_var=var,
            imports=["import re"],
            code_lines=code_lines,
            comment=f"Switch node ({mode} mode)",
        )
        ir_node.branches = branch_ir
        return ir_node

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.switch"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Merge Node
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.merge")
class MergeNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        mode = str(params.get("mode", "append")).lower()

        # Resolve all actual predecessor output variables from the DAG
        input_vars: list[str] = []
        G = ctx.dag
        if G.number_of_nodes() > 0:
            from backend.core.graph import get_merge_input_vars

            input_vars = get_merge_input_vars(G, node.name, ctx.var_context)

        # Fall back to current prev_var if DAG resolution yields nothing
        if not input_vars:
            input_vars = [prev_var]

        # Build comma-separated list for the merge expression
        inputs_list = ", ".join(input_vars)

        if mode == "append":
            code_lines = [
                f"# Merge (append): combine all input branches",
                f"{var}_inputs = []",
                f"for _branch in [{inputs_list}]:",
                f"    if isinstance(_branch, list):",
                f"        {var}_inputs.extend(_branch)",
                f"    else:",
                f"        {var}_inputs.append(_branch)",
                f"{var}_output = {var}_inputs",
            ]
        elif mode in ("keepmatches", "innerjoin"):
            join_key = ctx.resolve_expr(
                str(
                    params.get("joinMode", {})
                    .get("mergeByFields", {})
                    .get("clashHandling", "")
                    or params.get("propertyName1", "id")
                )
            )
            # Use first two inputs (or same list if only one)
            in1 = input_vars[0] if len(input_vars) >= 1 else prev_var
            in2 = input_vars[1] if len(input_vars) >= 2 else "[]"
            code_lines = [
                f"# Merge (inner join) by matching key",
                f"{var}_input1 = {in1}",
                f"{var}_input2 = {in2}",
                f"{var}_key = {join_key}",
                f"{var}_output = [",
                f"    {{**a['json'], **b['json']}}",
                f"    for a in {var}_input1",
                f"    for b in {var}_input2",
                f"    if a.get('json', {{}}).get({var}_key) == b.get('json', {{}}).get({var}_key)",
                f"]",
                f"{var}_output = [{{'json': item}} for item in {var}_output]",
            ]
        elif mode in ("keepeverything", "fullouter"):
            in1 = input_vars[0] if len(input_vars) >= 1 else prev_var
            in2 = input_vars[1] if len(input_vars) >= 2 else "[]"
            code_lines = [
                f"# Merge (outer join)",
                f"{var}_input1 = {in1}",
                f"{var}_input2 = {in2}",
                f"{var}_output = {var}_input1 + {var}_input2",
            ]
        elif mode in ("choosebranch", "passthrough"):
            branch_idx = int(params.get("chooseBranchMode", {}).get("output", 0) or 0)
            selected = (
                input_vars[branch_idx] if branch_idx < len(input_vars) else prev_var
            )
            code_lines = [
                f"# Merge (choose branch {branch_idx}): pass through selected branch",
                f"{var}_output = {selected}  # branch {branch_idx} selected",
            ]
        else:
            code_lines = [
                f"# Merge mode {mode!r} — combine all inputs",
                f"{var}_inputs = []",
                f"for _branch in [{inputs_list}]:",
                f"    if isinstance(_branch, list):",
                f"        {var}_inputs.extend(_branch)",
                f"    else:",
                f"        {var}_inputs.append(_branch)",
                f"{var}_output = {var}_inputs",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment=f"Merge ({mode})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.merge"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Split In Batches
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.splitInBatches")
class SplitInBatchesHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        batch_size = int(params.get("batchSize", 10))

        code_lines = [
            f"# Split In Batches: process {batch_size} items at a time",
            f"{var}_batch_size = {batch_size}",
            f"{var}_items = {prev_var}",
            f"{var}_output = []",
            f"for _i in range(0, len({var}_items), {var}_batch_size):",
            f"    {var}_batch = {var}_items[_i : _i + {var}_batch_size]",
            f"    # TODO: insert per-batch processing here",
            f"    {var}_output.extend({var}_batch)",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.FOR_LOOP,
            python_var=var,
            code_lines=code_lines,
            comment=f"Split In Batches (size={batch_size})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.splitInBatches"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Wait Node
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.wait")
class WaitNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resume_mode = str(params.get("resume", "timeInterval")).lower()

        if resume_mode == "timeinterval":
            amount = params.get("amount", 1)
            unit = str(params.get("unit", "hours")).lower()
            unit_map = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}
            secs = int(amount) * unit_map.get(unit, 3600)
            code_lines = [
                f"import time",
                f"time.sleep({secs})  # Wait: {amount} {unit}",
                f"{var}_output = {prev_var}",
            ]
        elif resume_mode == "webhook":
            path = params.get("webhookSuffix", "")
            code_lines = [
                f"# Wait for webhook resume at: /{path}",
                f"# TODO: implement webhook-resume logic",
                f"{var}_output = {prev_var}",
            ]
        else:
            code_lines = [
                f"# Wait node (mode={resume_mode!r}): pass-through",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import time"],
            code_lines=code_lines,
            comment=f"Wait ({resume_mode})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.wait"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Respond to Webhook
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.respondToWebhook")
class RespondToWebhookHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        respond_with = str(params.get("respondWith", "json")).lower()

        if respond_with == "json":
            response_body = (
                ctx.resolve_expr(str(params.get("responseBody", "")))
                or f'{prev_var}[0]["json"] if {prev_var} else {{}}'
            )
            code_lines = [
                f"# Respond to Webhook with JSON",
                f"{var}_response_body = {response_body}",
                f"return JSONResponse({var}_response_body)",
                f"{var}_output = {prev_var}",
            ]
        elif respond_with == "text":
            text_val = ctx.resolve_expr(str(params.get("responseBody", "OK")))
            code_lines = [
                f"from fastapi.responses import PlainTextResponse",
                f"return PlainTextResponse({text_val})",
                f"{var}_output = {prev_var}",
            ]
        elif respond_with == "redirect":
            url_val = ctx.resolve_expr(str(params.get("redirectURL", "")))
            code_lines = [
                f"from fastapi.responses import RedirectResponse",
                f"return RedirectResponse(url={url_val})",
                f"{var}_output = {prev_var}",
            ]
        else:
            code_lines = [
                f"# Respond to Webhook ({respond_with}): pass-through",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["from fastapi.responses import JSONResponse"],
            code_lines=code_lines,
            comment=f"Respond to Webhook (with={respond_with})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.respondToWebhook"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Stop and Error / No-op
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.stopAndError")
class StopAndErrorHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters
        error_msg = ctx.resolve_expr(
            str(params.get("errorMessage", "Workflow stopped by Stop and Error node"))
        )
        code_lines = [
            f"raise RuntimeError({error_msg})",
            f"{var}_output = {prev_var}",
        ]
        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.stopAndError"]

    def required_packages(self) -> list[str]:
        return []


@register("n8n-nodes-base.noOp")
class NoOpHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=[f"{var}_output = {prev_var}  # No-op pass-through"],
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.noOp"]

    def required_packages(self) -> list[str]:
        return []
