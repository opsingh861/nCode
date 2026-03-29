"""Code emitter: walks an IRProgram and produces a Python source string.

The emitter is intentionally the *only* place that writes Python text.
All handlers emit IRNode objects; this module turns them into code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from textwrap import indent
from typing import Union

from backend.core.ir import IRNode, IRNodeKind, IRProgram


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def emit_program(program: IRProgram) -> str:
    """Walk an IRProgram and return a Python source string."""
    parts: list[str] = []

    # 1. Header
    parts.append(_emit_header(program))

    # 2. Imports
    parts.append(_emit_imports(program))

    # 3. Body — FastAPI app vs script function
    if program.mode == "fastapi":
        parts.append(_emit_fastapi_body(program))
    else:
        parts.append(_emit_script_body(program))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def _emit_header(program: IRProgram) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        "# -*- coding: utf-8 -*-\n"
        f'"""Auto-generated from n8n workflow: {program.workflow_name!r}\n'
        f"Generated at: {ts}\n"
        f'"""\n'
    )


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

_STDLIB = frozenset({
    "abc", "ast", "base64", "collections", "contextlib", "csv", "dataclasses",
    "datetime", "enum", "functools", "hashlib", "hmac", "html", "http",
    "inspect", "io", "itertools", "json", "logging", "math", "operator",
    "os", "pathlib", "pprint", "queue", "random", "re", "shlex", "shutil",
    "signal", "smtplib", "socket", "sqlite3", "ssl", "string", "struct",
    "subprocess", "sys", "tempfile", "textwrap", "threading", "time",
    "traceback", "types", "typing", "unittest", "urllib", "uuid", "warnings",
    "xml", "zipfile",
})


def _import_sort_key(line: str) -> tuple[int, str]:
    """Returns (0=stdlib, 1=third-party, 2=local) + module name for sorting."""
    stripped = line.lstrip("from ").lstrip("import ")
    root = stripped.split(".")[0].split(" ")[0]
    if root in _STDLIB:
        return (0, root)
    if root.startswith(".") or root in ("backend",):
        return (2, root)
    return (1, root)

# Imports always injected so that expression-engine translations (math.floor,
# functools.reduce, random.random, re.search, etc.) work without handlers
# needing to explicitly track which functions were used in expressions.
_EXPRESSION_ENGINE_IMPORTS: frozenset[str] = frozenset({
    "import functools",
    "import json",
    "import math",
    "import os",
    "import random",
    "import re",
    "from datetime import datetime, date, timezone, timedelta",
})


def _emit_imports(program: IRProgram) -> str:
    all_imports = set(program.all_imports) | _EXPRESSION_ENGINE_IMPORTS
    sorted_imports = sorted(all_imports, key=_import_sort_key)
    # Insert blank lines between groups
    groups: list[list[str]] = [[], [], []]
    for imp in sorted_imports:
        groups[_import_sort_key(imp)[0]].append(imp)
    lines: list[str] = []
    for grp in groups:
        if grp:
            lines.extend(grp)
            lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# FastAPI body
# ---------------------------------------------------------------------------

def _emit_fastapi_body(program: IRProgram) -> str:
    parts: list[str] = []

    # App instantiation (only once — imports are in _emit_imports already)
    parts.append("app = FastAPI()\n")

    if not program.nodes:
        parts.append("# WARNING: No nodes to emit\n")
        return "\n".join(parts)

    # Find the first trigger node that opens a route function (has @app. in code).
    trigger_idx: int | None = None
    for i, ir_node in enumerate(program.nodes):
        code = "\n".join(ir_node.code_lines)
        if "@app." in code or "async def " in code:
            trigger_idx = i
            break

    if trigger_idx is not None:
        # Nodes before the trigger (shouldn't normally exist in fastapi mode)
        for ir_node in program.nodes[:trigger_idx]:
            parts.append(_emit_node(ir_node, indent_level=0))

        # Trigger node opens the route function — emit at top level
        parts.append(_emit_node(program.nodes[trigger_idx], indent_level=0))

        # All subsequent nodes are INSIDE the route function (indented by 1)
        body_nodes = program.nodes[trigger_idx + 1:]
        for ir_node in body_nodes:
            parts.append(_emit_node(ir_node, indent_level=1))

        # If last body node didn't include a top-level `return`, add a default one.
        # Check only the last non-empty direct code line (not lines inside nested
        # functions/loops which may have their own return statements).
        if body_nodes:
            last_direct_lines = [
                ln for ln in body_nodes[-1].code_lines if ln.strip()
            ]
            last_direct_line = last_direct_lines[-1].strip() if last_direct_lines else ""
            has_return = last_direct_line.startswith("return ")
            if not has_return:
                last_var = body_nodes[-1].python_var
                parts.append(
                    f"    return JSONResponse({last_var}_output[0]['json'] "
                    f"if {last_var}_output else {{}})"
                )
        else:
            # No body nodes — insert minimal return
            trigger_var = program.nodes[trigger_idx].python_var
            parts.append(
                f"    return JSONResponse({trigger_var}_output[0]['json'] "
                f"if {trigger_var}_output else {{}})"
            )
    else:
        # No trigger found — emit all at top level
        for ir_node in program.nodes:
            parts.append(_emit_node(ir_node, indent_level=0))
    parts.append('\nif __name__ == "__main__":')
    parts.append('    uvicorn.run("__main__:app", host="0.0.0.0", port=8000, reload=False)')

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Script body
# ---------------------------------------------------------------------------

def _emit_script_body(program: IRProgram) -> str:
    parts: list[str] = []

    if not program.nodes:
        parts.append("# WARNING: No nodes to emit\n")
        return "\n".join(parts)

    parts.append("def run_workflow():")
    # Emit all nodes indented inside the function
    body_lines: list[str] = []
    for ir_node in program.nodes:
        node_src = _emit_node(ir_node, indent_level=0)
        body_lines.append(indent(node_src, "    "))
    body = "\n".join(body_lines)
    if not body.strip():
        body = "    pass"
    parts.append(body)

    # Return last output if available
    if program.nodes:
        last_var = program.nodes[-1].python_var
        parts.append(f"    return {last_var}_output")

    parts.append("\n")
    parts.append('if __name__ == "__main__":')
    parts.append("    import json")
    parts.append("    result = run_workflow()")
    parts.append("    print(json.dumps(result, indent=2, default=str))")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Node emitter (recursive)
# ---------------------------------------------------------------------------

def _emit_node(ir_node: IRNode, indent_level: int = 0) -> str:
    """Emit a single IRNode as Python source, handling branches recursively."""
    prefix = "    " * indent_level
    lines: list[str] = []

    if ir_node.comment:
        lines.append(f"{prefix}# --- {ir_node.comment} ---")

    if ir_node.kind == IRNodeKind.STATEMENT:
        for line in ir_node.code_lines:
            lines.append(f"{prefix}{line}" if line.strip() else line)

    elif ir_node.kind == IRNodeKind.IF_BRANCH:
        # code_lines contains ONLY the `if condition:` line.
        # Branches: "true_branch" nodes go inside the if block,
        #           "false_branch" nodes go inside the else block,
        #           "_epilogue_lines" nodes go after the else block.
        cond_line = ir_node.code_lines[0] if ir_node.code_lines else "if True:"
        lines.append(f"{prefix}{cond_line}")

        true_nodes = ir_node.branches.get("true_branch", [])
        if true_nodes:
            for child in true_nodes:
                lines.append(_emit_node(child, indent_level + 1))
        else:
            lines.append(f"{prefix}    pass")

        lines.append(f"{prefix}else:")
        false_nodes = ir_node.branches.get("false_branch", [])
        if false_nodes:
            for child in false_nodes:
                lines.append(_emit_node(child, indent_level + 1))
        else:
            lines.append(f"{prefix}    pass")

        # Epilogue — unified output variable assignment after the if/else
        for epi_node in ir_node.branches.get("_epilogue_lines", []):
            lines.append(_emit_node(epi_node, indent_level))

    elif ir_node.kind == IRNodeKind.SWITCH_BRANCH:
        # code_lines is the full if/elif/else switch body.
        for line in ir_node.code_lines:
            lines.append(f"{prefix}{line}" if line.strip() else line)
        # Branch child nodes are emitted at the current indent level (after the switch block).
        for branch_key, branch_nodes in sorted(ir_node.branches.items()):
            if branch_key.startswith("_"):
                continue  # skip internal/epilogue keys
            if branch_nodes:
                lines.append(f"{prefix}# {branch_key.replace('_', ' ')} nodes")
                for child in branch_nodes:
                    lines.append(_emit_node(child, indent_level))

    elif ir_node.kind == IRNodeKind.FOR_LOOP:
        for line in ir_node.code_lines:
            lines.append(f"{prefix}{line}" if line.strip() else line)
        for child in ir_node.loop_body:
            lines.append(_emit_node(child, indent_level + 1))

    elif ir_node.kind == IRNodeKind.FUNCTION_DEF:
        for line in ir_node.code_lines:
            lines.append(f"{prefix}{line}" if line.strip() else line)

    elif ir_node.kind == IRNodeKind.TRY_EXCEPT:
        for line in ir_node.code_lines:
            lines.append(f"{prefix}{line}" if line.strip() else line)

    else:
        # Fallback: plain statement
        for line in ir_node.code_lines:
            lines.append(f"{prefix}{line}" if line.strip() else line)

    lines.append("")  # blank line after each node block
    return "\n".join(lines)
