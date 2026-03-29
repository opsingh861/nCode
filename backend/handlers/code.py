"""Code node handler: JavaScript → Python best-effort translation."""

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


# Simple JS patterns that can be mechanically translated.
_SIMPLE_PATTERNS = [
    # variable declarations
    (re.compile(r"\bconst\b"), ""),
    (re.compile(r"\blet\b"), ""),
    (re.compile(r"\bvar\b"), ""),
    # console.log
    (re.compile(r"\bconsole\.log\("), "print("),
    # arrow functions (simple single-expression)
    (re.compile(r"\((\w+)\)\s*=>\s*\{"), r"lambda \1:"),
    # JSON.parse / JSON.stringify
    (re.compile(r"\bJSON\.parse\("), "__import__('json').loads("),
    (re.compile(r"\bJSON\.stringify\("), "__import__('json').dumps("),
    # null/undefined/true/false
    (re.compile(r"\bnull\b"), "None"),
    (re.compile(r"\bundefined\b"), "None"),
    (re.compile(r"\btrue\b"), "True"),
    (re.compile(r"\bfalse\b"), "False"),
    # operators
    (re.compile(r"==="), "=="),
    (re.compile(r"!=="), "!="),
    (re.compile(r"\&\&"), "and"),
    (re.compile(r"\|\|"), "or"),
    # string methods
    (re.compile(r"\.toLowerCase\(\)"), ".lower()"),
    (re.compile(r"\.toUpperCase\(\)"), ".upper()"),
    (re.compile(r"\.trim\(\)"), ".strip()"),
    (re.compile(r"\.toString\(\)"), ".__str__()"),
    (re.compile(r"\.startsWith\("), ".startswith("),
    (re.compile(r"\.endsWith\("), ".endswith("),
    # return statement (kept as-is in Python)
    (re.compile(r"\breturn\b"), "return"),
]

# Patterns that indicate code is too complex for simple translation.
_COMPLEX_PATTERN = re.compile(
    r"\.(map|filter|reduce|forEach|find|findIndex|every|some)\s*\(.*?=>"
    r"|class\s+\w+|new\s+\w+\s*\("
    r"|require\s*\(",
    re.DOTALL,
)


def _translate_js_to_python(js_code: str) -> tuple[str, bool]:
    """Best-effort JS → Python translation.

    Returns (translated_code, was_complex) where was_complex=True means
    the code likely needs manual review.
    """
    is_complex = bool(_COMPLEX_PATTERN.search(js_code))

    lines = js_code.splitlines()
    result_lines = []

    for line in lines:
        translated = line
        for pattern, replacement in _SIMPLE_PATTERNS:
            translated = pattern.sub(replacement, translated)

        # Remove trailing semicolons
        translated = re.sub(r";\s*$", "", translated)
        # Handle basic {} → : (function bodies) — very rough
        translated = re.sub(r"\{\s*$", ":", translated)
        # Remove standalone }
        stripped = translated.strip()
        if stripped == "}":
            continue

        result_lines.append(translated)

    return "\n".join(result_lines), is_complex


@register("n8n-nodes-base.code")
class CodeNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        language = str(params.get("language", "javaScript")).lower()
        mode = str(params.get("mode", "runOnceForAllItems")).lower()

        warnings = []
        code_lines = []

        if "python" in language:
            # Python code — include verbatim
            py_code = str(params.get("pythonCode", params.get("jsCode", "# empty")))
            code_lines = [
                f"# Code node (Python) — verbatim from n8n",
                f"# --- begin user code ---",
            ]
            for line in py_code.splitlines():
                code_lines.append(line)
            code_lines += [
                f"# --- end user code ---",
                f"# Ensure {var}_output is assigned above, or use pass-through:",
                f"{var}_output = {var}_output if '{var}_output' in dir() else {prev_var}",
            ]
        else:
            # JavaScript code — best-effort translation
            js_code = str(params.get("jsCode", params.get("code", "// empty")))

            if not js_code.strip() or js_code.strip() in ("// empty", ""):
                code_lines = [f"{var}_output = {prev_var}  # Code node: empty"]
            else:
                translated, is_complex = _translate_js_to_python(js_code)

                if is_complex:
                    warnings.append(
                        f"Code node '{node.name}': complex JavaScript detected — manual review required"
                    )
                    code_lines = [
                        f"# Code node: complex JavaScript — manual translation required",
                        f"# Original JS:",
                    ]
                    for js_line in js_code.splitlines():
                        code_lines.append(f"# {js_line}")
                    code_lines += [
                        f"# --- TODO: implement the above in Python ---",
                        f"{var}_output = {prev_var}  # pass-through until implemented",
                    ]
                else:
                    code_lines = [
                        f"# Code node: best-effort JS→Python translation",
                        f"# Review carefully before use",
                        f"items = {prev_var}",
                    ]
                    for py_line in translated.splitlines():
                        code_lines.append(py_line)
                    code_lines += [
                        f"# Capture return_data if user code sets it:",
                        f"{var}_output = return_data if 'return_data' in dir() else items",
                    ]

        for w in warnings:
            ctx.warn(w, node.name)

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            warnings=warnings,
            comment=f"Code node ({language}, {mode})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.code"]

    def required_packages(self) -> list[str]:
        return []
