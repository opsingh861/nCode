---
layout: default
title: Architecture
nav_order: 3
description: "Deep dive into the nCode transpiler pipeline — IR, graph, expression engine, emitter, and post-processor."
---

# Architecture
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Overview

nCode is a **multi-stage source-to-source transpiler**. An n8n workflow is a directed acyclic graph (DAG) of nodes connected by typed edges. nCode walks that DAG in topological order, dispatches each node to a handler, and assembles an intermediate representation (IR) that is then emitted as Python source.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         nCode Pipeline                              │
│                                                                     │
│  JSON input                                                         │
│      │                                                              │
│      ▼                                                              │
│  ① Parse & Validate  ── Pydantic: N8nWorkflow, N8nNode             │
│      │                                                              │
│      ▼                                                              │
│  ② Build DAG  ── networkx DiGraph; edge metadata                   │
│      │          (connection_type, branch_index)                     │
│      ▼                                                              │
│  ③ Topological Sort  ── cycle-safe execution order                 │
│      │                                                              │
│      ▼                                                              │
│  ④ Mode Detection  ── trigger node type → script | fastapi         │
│      │                                                              │
│      ▼                                                              │
│  ⑤ Handler Dispatch  ── @register decorator map                    │
│      │                   NodeHandler.generate() → IRNode           │
│      ▼                                                              │
│  ⑥ IR → Python  ── emitter.py walks IRProgram                     │
│      │                                                              │
│      ▼                                                              │
│  ⑦ Post-Process  ── black + isort + py_compile syntax check       │
│      │                                                              │
│      ▼                                                              │
│  ZIP artifact  (main.py · requirements.txt · .env.example)         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Repository layout

```text
backend/
  core/
    ir.py                # IRNode, IRProgram, IRNodeKind
    graph.py             # DAG builder + topological sort + merge detection
    expression_engine.py # n8n {{ }} template → Python translator
    emitter.py           # IRProgram → Python source string
    post_processor.py    # black + isort + py_compile
    pipeline.py          # Orchestrates all stages
  handlers/
    registry.py          # @register decorator + handler lookup
    base.py              # GenerationContext (shared mutable state)
    triggers.py          # Manual, Webhook, Schedule, Chat triggers
    http.py              # HTTP Request node
    flow_control.py      # IF, Switch, Merge, SplitInBatches
    data_transform.py    # Set, Filter, Item Lists
    code.py              # Code node (Python pass-through / JS stub)
    databases.py         # Postgres, MySQL, MongoDB stubs
    apps.py              # Slack, Notion, Airtable, Google Sheets stubs
    ai_langchain.py      # LangChain Agent, LLMs, Memory, Tools
    fallback.py          # Catch-all TODO stub for unknown types
    __init__.py          # Imports all handler modules (triggers @register)
  models/
    workflow.py          # N8nWorkflow, N8nNode (Pydantic)
    response.py          # PipelineResult
  routers/
    generate.py          # FastAPI routes: /api/upload, /api/download
  tests/
    test_expression_engine.py
    test_graph.py
    test_handlers.py
    test_pipeline.py
```

---

## Stage 1 — Parse & Validate

`N8nWorkflow` and `N8nNode` are **Pydantic v2 models**. Pydantic rejects malformed input before any code runs, ensuring all downstream stages receive well-typed data.

```python
class N8nNode(BaseModel):
    id: str
    name: str
    type: str
    typeVersion: float
    parameters: dict[str, Any]
    credentials: dict[str, Any] = {}
```

---

## Stage 2 — Build DAG

`graph.py` constructs a `networkx.DiGraph` from the `connections` map in the workflow JSON. Each edge carries metadata:

```python
{
    "connection_type": "main" | "ai_tool" | "ai_memory" | "ai_llm" | ...,
    "branch_index": int   # 0 = true branch, 1 = false branch for IF nodes
}
```

The DAG builder also detects **AI sub-node composition** — nodes connected via `ai_tool`, `ai_memory`, or `ai_llm` edges are composed *inside* their root agent node's Python block, not emitted as separate steps.

---

## Stage 3 — Topological Sort & Merge Detection

`topological_order()` returns nodes in execution order. After sorting, `find_merge_point()` uses `nx.immediate_dominators()` to locate the convergence node after an IF branch, enabling correct branch scoping in the emitter.

---

## Stage 4 — Mode Detection

The trigger node type controls the entire output shape:

| Trigger type | Output mode | Entry point |
|---|---|---|
| `manualTrigger`, `scheduleTrigger` | `script` | `def run_workflow():` + `if __name__ == "__main__"` |
| `webhook`, `chatTrigger`, etc. | `fastapi` | `@app.post("/path")` async route |

---

## Stage 5 — Handler Dispatch

Every handler is a class decorated with `@register("n8n-nodes-base.nodeType")`. The registry is a simple `dict[str, NodeHandler]`. Handlers implement three methods:

```python
class NodeHandler(Protocol):
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode: ...
    def supported_operations(self) -> list[str]: ...
    def required_packages(self) -> list[str]: ...
```

`GenerationContext` is a **shared mutable object** threaded through all handlers:

- `ctx.add_import(statement)` — collects `import` lines
- `ctx.add_package(name)` — collects `requirements.txt` entries
- `ctx.register_node_var(name, var)` — maps node names → Python variable names
- `ctx.processed_nodes` — a `set` preventing double-emission of branch sub-nodes

---

## Stage 6 — IR → Python (Emitter)

`IRNode` carries:

| Field | Type | Description |
|---|---|---|
| `kind` | `IRNodeKind` | `STATEMENT`, `IF_BRANCH`, `SWITCH_BRANCH`, `FOR_LOOP`, `FUNCTION_DEF`, `TRY_EXCEPT` |
| `python_var` | `str` | The variable name for this node's output (`{var}_output`) |
| `code_lines` | `list[str]` | The raw Python lines to emit |
| `children` | `list[IRNode]` | Nested IR (true/false branches, loop body, etc.) |

The emitter does a recursive walk of the `IRProgram` tree and assembles the final source string.

---

## Stage 7 — Post-Processing

1. **`black`** — enforces PEP 8 formatting (88-char line limit)
2. **`isort`** — sorts and groups import statements
3. **`py_compile.compile()`** — catches syntax errors in generated code before the ZIP is assembled

If formatting fails (e.g., a handler emitted invalid Python), the raw unformatted source is returned with a warning instead of failing the request.

---

## Data-Flow Contract

Every node input and output is `list[dict]`, where each dict has at minimum:

```python
{"json": {...}}    # the payload fields for this item
```

This mirrors n8n's own data model. All handlers must maintain this shape — never flatten or unwrap items.

---

## Expression Engine

The expression engine (`expression_engine.py`) is a **recursive-descent parser + translator** for n8n's `{{ }}` template syntax. It handles:

| n8n expression | Generated Python |
|---|---|
| `{{ $json.field }}` | `item["json"]["field"]` |
| `{{ $env.VAR_NAME }}` | `os.getenv("VAR_NAME")` |
| `{{ $now }}` | `datetime.now(timezone.utc)` |
| `{{ $('Node').json.path }}` | `node_output[0]["json"]["path"]` |
| `{{ $fromAI('key') }}` | `agent_context.get("key")` |
| JS ternary `a ? b : c` | `b if a else c` |
| `===`, `&&`, `\|\|` | `==`, `and`, `or` |

---

## Security Design

- Uploaded JSON is parsed as **data** only — never `eval`'d or `exec`'d server-side.
- All credential values discovered in node parameters are replaced with `os.getenv("NAME")`.
- Download IDs are **UUID4** (cryptographically random) — no path traversal is possible.
- Generated code is returned to the *user* to run locally; nCode never executes it.
