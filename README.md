# nCode

Convert n8n workflow JSON into runnable Python projects.

[![CI](https://github.com/opsingh861/nCode/actions/workflows/ci.yml/badge.svg)](https://github.com/opsingh861/nCode/actions/workflows/ci.yml)
[![CodeQL](https://github.com/opsingh861/nCode/actions/workflows/codeql.yml/badge.svg)](https://github.com/opsingh861/nCode/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![Status](https://img.shields.io/badge/Status-Active-success)

[Documentation](https://opsingh861.github.io/nCode/) · [Report a Bug](https://github.com/opsingh861/nCode/issues/new?template=bug_report.yml) · [Request a Feature](https://github.com/opsingh861/nCode/issues/new?template=feature_request.yml)

## Why nCode

nCode is an open-source transpiler that takes exported n8n workflows and generates a Python project you can run immediately.

Key outcomes:

- Converts n8n nodes into Python code with a deterministic pipeline.
- Auto-detects output mode:
  - FastAPI mode for webhook/chat-triggered workflows.
  - Script mode for manual/schedule or non-HTTP workflows.
- Generates project artifacts you can run/share:
  - `main.py`
  - `requirements.txt`
  - `.env.example`
  - `README.md`
  - `workflow_meta.json`
- Preserves unsupported nodes as explicit TODO stubs instead of failing the full generation.

## Architecture at a Glance

Backend pipeline flow:

1. Parse JSON into Pydantic models.
2. Build a DAG from workflow nodes and connections.
3. Topologically order executable nodes.
4. Detect output mode (`fastapi` or `script`) from trigger node types.
5. Dispatch per-node handlers to emit IR.
6. Emit Python source from IR.
7. Run post-processing (black + isort + syntax checks).

Core folders:

- `backend/core/`: graph, IR, expression translation, emitter, pipeline.
- `backend/handlers/`: one handler class per node type family.
- `backend/models/`: request/response and workflow Pydantic models.
- `backend/routers/`: FastAPI router endpoints.
- `frontend/src/`: React + Vite user interface.
- `docs/`: project documentation site content.

## Supported Node Types

The registry currently exposes **107** supported node-type strings (including aliases and specialized LangChain node types).

For the exact runtime list in your local checkout:

- Use API endpoint: `GET /api/supported-nodes`
- Or inspect handlers under `backend/handlers/`

Design principle:

- Supported nodes generate concrete Python blocks.
- Unsupported nodes still produce runnable pass-through stubs with TODO comments.

## Prerequisites

- Python 3.10+
- Node.js 18+
- Docker 24+ (optional)

## Quick Start

### Option 1: Local development

```bash
git clone https://github.com/opsingh861/nCode.git
cd nCode

# Backend environment
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS/Linux
# source .venv/bin/activate

cd ..
pip install -r requirements.txt

# Optional environment customization
# Windows PowerShell: Copy-Item .env.example .env
# macOS/Linux: cp .env.example .env

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open API docs at `http://localhost:8000/docs`.

### Option 2: Full stack dev helper script

From repo root:

```bash
./run-dev.sh
```

This starts:

- backend at `http://0.0.0.0:8000`
- frontend at `http://localhost:3000`

Note: the script expects backend Python at `backend/.venv/Scripts/python.exe`.

### Option 3: Docker Compose

```bash
docker compose up --build
```

Services:

- frontend: `http://localhost:3000`
- backend API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`

## API Reference

### Primary endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/api/upload` | Upload `workflow.json`, run pipeline, return generated preview + `download_id` |
| `GET` | `/api/download/{download_id}` | Download generated ZIP for a previous upload |
| `POST` | `/api/generate` | Direct JSON transpilation endpoint (no multipart upload) |
| `GET` | `/api/supported-nodes` | Get all registered node type strings |

### cURL examples

Upload flow:

```bash
curl -X POST "http://127.0.0.1:8000/api/upload" -F "file=@workflow.json"
```

Download artifact:

```bash
curl -L "http://127.0.0.1:8000/api/download/<download_id>" -o workflow_python.zip
```

Direct JSON generate flow:

```bash
curl -X POST "http://127.0.0.1:8000/api/generate" \
  -H "Content-Type: application/json" \
  --data @workflow.json
```

## Frontend

The UI is built with React + TypeScript + Vite and proxies `/api` calls to `http://localhost:8000` in development.

```bash
cd frontend
npm install
npm run dev
```

## Development and Contribution

See `CONTRIBUTING.md` for full guidelines. Common local checks:

```bash
# Tests
backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v

# Formatting checks (CI-aligned)
backend\.venv\Scripts\python.exe -m black --check backend/
backend\.venv\Scripts\python.exe -m isort --check-only --profile black backend/
```

### Adding a new node handler

1. Create or update a handler file in `backend/handlers/`.
2. Register node types with `@register("node.type")`.
3. Implement the handler interface (`generate`, `supported_operations`, `required_packages`).
4. Import the module in `backend/handlers/__init__.py` so registration runs.

## Security Notes

- Credentials are emitted as environment variable lookups (`os.getenv(...)`) rather than embedded secrets.
- Upload flow enforces JSON extension and file size constraints.
- Download IDs are UUID-validated to prevent path traversal.
- Temporary artifact cleanup runs during app lifecycle shutdown.
- CORS origins are explicit (configured by `CORS_ALLOW_ORIGINS` or safe local defaults).

## Project Structure

```text
nCode/
|-- backend/
|   |-- core/
|   |-- handlers/
|   |-- models/
|   |-- routers/
|   `-- main.py
|-- frontend/
|   `-- src/
|-- docs/
|-- requirements.txt
|-- run-dev.sh
`-- docker-compose.yml
```

## Documentation

- Docs site: https://opsingh861.github.io/nCode/
- Architecture: docs/architecture.md
- Getting started: docs/getting-started.md
- Node handlers: docs/node-handlers.md
- API reference: docs/api-reference.md

## License

MIT. See `LICENSE`.