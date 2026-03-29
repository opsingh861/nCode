# nCode — Copilot Instructions

n8n workflow JSON → executable Python transpiler. FastAPI backend + React/Vite frontend.

## Architecture

```
backend/core/        # Pipeline stages: ir → graph → expression_engine → emitter → post_processor
backend/handlers/    # One class per n8n node type, registered via @register decorator
backend/models/      # Pydantic models: N8nWorkflow, N8nNode, PipelineResult
frontend/src/        # React + TypeScript; API calls via api/client.ts (proxied to :8000)
```

Pipeline flow: `parse → build_dag → topo_sort → mode_detect → emit_IR → emit_code → format`

Two output modes, detected automatically from the trigger node type:
- **script**: `manualTrigger` / `scheduleTrigger` → bare `if __name__ == "__main__"` block
- **fastapi**: `webhook` / `chatTrigger` → Pydantic models + async route handlers

## Build & Test

```bash
# Backend dev server (activates backend/.venv automatically)
./run-dev.sh

# Tests (no pytest.ini — vanilla discovery)
backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v

# Formatting checks (match CI behavior)
backend\.venv\Scripts\python.exe -m black --check backend/
backend\.venv\Scripts\python.exe -m isort --check-only --profile black backend/

# Frontend dev (Vite, proxies /api → :8000)
cd frontend && npm run dev

# Full stack
docker compose up --build
```

Backend venv lives at `backend/.venv/`. `load_dotenv()` runs at startup; no required env vars — everything has defaults or is optional.

Frontend lockfile note: keep `frontend/package-lock.json` tracked in git because CI uses `npm ci` and `actions/setup-node` npm cache keyed from that lockfile.

Security/release note: backend dependency automation must target the repo root (`/`) because the canonical Python dependency file is the top-level `requirements.txt`, not `backend/requirements.txt`.

Security note: backend CORS must use explicit origins from `CORS_ALLOW_ORIGINS` (comma-separated) or the local dev defaults; do not combine `allow_credentials=True` with wildcard origins.

## Adding a Handler

1. Create or extend a file in `backend/handlers/`
2. Decorate with `@register("n8n-nodes-base.yourType")`
3. Implement the three-method `NodeHandler` protocol:

```python
from backend.handlers.registry import register
from backend.handlers.base import GenerationContext
from backend.core.ir import IRNode, IRNodeKind
from backend.models.workflow import N8nNode

@register("n8n-nodes-base.myNode")
class MyNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)          # regex: [^a-zA-Z0-9]+ → "_", prefix "n_" if digit-leading
        ctx.register_node_var(node.name, var)
        ctx.add_import("import something")
        ctx.add_package("some-package")
        return IRNode(
            node_id=node.id, node_name=node.name,
            kind=IRNodeKind.STATEMENT, python_var=var,
            code_lines=[f"{var}_output = ..."],
        )

    def supported_operations(self) -> list[str]: return ["operationName"]
    def required_packages(self) -> list[str]: return ["some-package"]
```

4. Import the module in `backend/handlers/__init__.py` (triggers `@register` side-effect).

## Key Conventions

**Data flow contract** — every node input/output is `list[dict]` where each dict has `{"json": {...}}`. Never break this shape.

**`GenerationContext` is shared and mutable** — `ctx.processed_nodes` (`set`) prevents double-emitting branch sub-nodes. Branch recursion in `flow_control.py` marks nodes there; the top-level loop skips via `if node_name in visited`.

**Never hard-fail on unsupported nodes** — exceptions in `generate()` → error stub (from `fallback.py`). Partial generation is preferred. Unsupported nodes get a pass-through TODO comment.

**Generated variable naming** — always `{python_var}_output`. `_safe_var()` is defined locally in each handler file; duplicate the small function rather than importing it.

**LangChain memory nodes** — generated `requirements.txt` must include both `langchain` and `langchain-classic` when `ConversationBuffer*Memory` is used.

**Generated FastAPI routes** — use typed Pydantic request models (not raw `Request`) so params appear in OpenAPI/Swagger.

## Frontend Conventions

- HTTP calls go through `frontend/src/api/client.ts` — do not `fetch()` directly in components.
- TypeScript types use `interface`, not `type` aliases — see `frontend/src/types/api.ts`.
- No runtime validation (no Zod) — types are cast directly from `response.json()`.

!important: If something is being changed in the code which we want Copilot to learn from, please also add it to this instructions file with a note. Copilot learns from the instructions file, so if you want it to learn something, it needs to be in here.