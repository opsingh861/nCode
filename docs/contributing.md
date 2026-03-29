---
layout: default
title: Contributing
nav_order: 6
description: "How to contribute to nCode — bug reports, new node handlers, tests, and documentation."
---

# Contributing to nCode
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

Thank you for considering a contribution! nCode is open source under the MIT License and welcomes all contributions — from bug reports and documentation improvements to full node handler implementations.

---

## Code of Conduct

All contributors are expected to follow the [Contributor Covenant Code of Conduct](https://github.com/opsingh861/nCode/blob/main/CODE_OF_CONDUCT.md). Please read it before participating.

---

## Ways to Contribute

| Contribution type | Where to start |
|---|---|
| Report a bug | [Bug Report issue template](https://github.com/opsingh861/nCode/issues/new?template=bug_report.yml) |
| Request a feature | [Feature Request issue template](https://github.com/opsingh861/nCode/issues/new?template=feature_request.yml) |
| Request a new node handler | [Node Handler Request template](https://github.com/opsingh861/nCode/issues/new?template=node_handler_request.yml) |
| Browse open tasks | [Issues labelled `good first issue`](https://github.com/opsingh861/nCode/issues?q=label%3A%22good+first+issue%22) |
| Ask a question | [GitHub Discussions — Q&A](https://github.com/opsingh861/nCode/discussions/categories/q-a) |

---

## Development Setup

```bash
git clone https://github.com/opsingh861/nCode.git
cd nCode

# Backend
cd backend
python -m venv .venv
# Windows:  .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r ../requirements.txt

# Frontend (optional)
cd ../frontend
npm install
```

Run all tests before making changes to establish a baseline:

```bash
backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v
```

---

## Adding a Node Handler

This is the most impactful contribution. Here is the complete pattern:

### 1. Create or extend a handler file

Add your class to an existing file in `backend/handlers/` (e.g., `apps.py` for SaaS integrations) or create a new file.

```python
# backend/handlers/apps.py  (or a new file)
import re
from backend.handlers.registry import register
from backend.handlers.base import GenerationContext
from backend.core.ir import IRNode, IRNodeKind
from backend.models.workflow import N8nNode


def _safe_var(name: str) -> str:
    var = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return f"n_{var}" if var[0].isdigit() else var


@register("n8n-nodes-base.myNode")
class MyNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        ctx.register_node_var(node.name, var)
        ctx.add_import("import my_library")
        ctx.add_package("my-library>=1.0")

        code = [
            f"# MyNode: {node.name}",
            f"{var}_output = [",
            f'    {{"json": my_library.do_something()}}',
            f"]",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code,
        )

    def supported_operations(self) -> list[str]:
        return ["defaultOperation"]

    def required_packages(self) -> list[str]:
        return ["my-library"]
```

### 2. Register the import

Add an import at the bottom of `backend/handlers/__init__.py` to trigger the `@register` side-effect:

```python
from backend.handlers import apps  # noqa: F401 — registers handlers
```

### 3. Write tests

Add test cases in `backend/tests/test_handlers.py`:

```python
def test_my_node_generates_valid_code():
    node = N8nNode(
        id="1", name="My Node", type="n8n-nodes-base.myNode",
        typeVersion=1.0, parameters={"operation": "defaultOperation"},
    )
    ctx = GenerationContext()
    ir = MyNodeHandler().generate(node, ctx)

    assert ir.python_var == "my_node"
    assert any("my_library" in line for line in ir.code_lines)
    assert "my-library" in MyNodeHandler().required_packages()
```

### 4. Key rules for handlers

{: .highlight }
> **Data-flow contract:** Every handler output must be `list[dict]` where each dict has `{"json": {...}}`. Never break this shape.

- Use `{python_var}_output` as the variable name for the node's result.
- Use `_safe_var()` (defined locally in each handler file — copy the small function, do not import).
- When a path is unsupported, emit a `# TODO` comment and pass items through — **never raise an exception**.
- Credentials must use `os.getenv("CREDENTIAL_NAME")`, never hard-coded values.

---

## Coding Standards

### Python

- PEP 8 style — enforced by `black` (88-char line limit) and `isort`
- Type hints on all public functions
- No `Any` without justification

### TypeScript / React

- `interface` declarations (not `type` aliases) — see `frontend/src/types/api.ts`
- Strict TypeScript — no implicit `any`
- HTTP calls through `frontend/src/api/client.ts` only — no direct `fetch()` in components
- Functional components with hooks

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(handlers): add full Slack send-message handler
fix(expression-engine): handle nested ternary with method chain
docs(architecture): add post-dominator merge detection explanation
test(handlers): add Slack handler unit tests
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

---

## Pull Request Checklist

Before opening a PR:

- [ ] All tests pass: `pytest backend/tests/ -v`
- [ ] Code is formatted: `black backend/` and `isort backend/`
- [ ] Frontend builds if you changed frontend files: `npm run build`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] PR description uses the [PR template](https://github.com/opsingh861/nCode/blob/main/.github/PULL_REQUEST_TEMPLATE.md)

---

## Project Roadmap

See [open issues](https://github.com/opsingh861/nCode/issues) and the [Discussions — Ideas](https://github.com/opsingh861/nCode/discussions/categories/ideas) board for the current roadmap.

High-priority areas:

1. Full Slack, Notion, and Google Sheets handler implementations
2. Switch node full expression support
3. `splitInBatches` → Python `for` loop with `itertools.islice`
4. Merge node strategies (append, combine, multiplex)
5. JavaScript `code` node → Python best-effort transpilation
