"""Intermediate Representation (IR) types for the n8n-to-Python transpiler.

Every node in the transpiled workflow maps to an IRNode. The emitter walks
the IR tree and produces Python source without any string manipulation in
handler code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IRNodeKind(Enum):
    """Classifies the structural role of an IR node in the generated program."""

    STATEMENT = "statement"        # Simple sequential statement(s)
    IF_BRANCH = "if_branch"        # if/elif/else conditional
    SWITCH_BRANCH = "switch_branch"  # Multi-way switch/match
    FOR_LOOP = "for_loop"          # For loop (split-in-batches etc.)
    FUNCTION_DEF = "function_def"  # Function definition
    TRY_EXCEPT = "try_except"      # try/except block


@dataclass
class IRNode:
    """A single unit of generated Python logic derived from one n8n node.

    Attributes:
        node_id:      The n8n node UUID.
        node_name:    The display name of the n8n node.
        kind:         The structural kind of this IR unit.
        python_var:   Safe Python variable stem (e.g. "http_request").
                      The output variable is ``{python_var}_output``.
        imports:      Module import statements needed by this node's code.
        pip_packages: pip package names required at runtime.
        code_lines:   The Python source lines for this node (not indented).
        branches:     For IF_BRANCH: keys "true" / "false" / output indices.
                      For SWITCH_BRANCH: keys are branch labels / indices.
                      Values are lists of IRNode for each branch body.
        loop_body:    Child IRNodes executed inside a FOR_LOOP.
        comment:      Optional explanatory comment emitted above the block.
        warnings:     Transpilation warnings specific to this node.
    """

    node_id: str
    node_name: str
    kind: IRNodeKind
    python_var: str
    imports: list[str] = field(default_factory=list)
    pip_packages: list[str] = field(default_factory=list)
    code_lines: list[str] = field(default_factory=list)
    branches: dict[str, list["IRNode"]] = field(default_factory=dict)
    loop_body: list["IRNode"] = field(default_factory=list)
    comment: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class IRProgram:
    """The complete transpiled workflow as an IR structure.

    Consumed by the emitter to produce final Python source.

    Attributes:
        workflow_name: Original n8n workflow display name.
        nodes:         Top-level IR nodes in execution order.
        all_imports:   Union of all imports required by all nodes.
        all_packages:  Union of all pip packages required.
        mode:          "fastapi" for HTTP-triggered workflows, "script" otherwise.
        warnings:      Pipeline-level warnings (not node-specific).
        trigger_info:  Dict with trigger metadata (method, path, type, etc.).
    """

    workflow_name: str
    nodes: list[IRNode]
    all_imports: set[str] = field(default_factory=set)
    all_packages: set[str] = field(default_factory=set)
    mode: str = "script"  # "fastapi" | "script"
    warnings: list[str] = field(default_factory=list)
    trigger_info: dict = field(default_factory=dict)
