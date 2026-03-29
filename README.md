# nCode

> Convert n8n workflows to clean, runnable Python code

[![CI](https://github.com/opsingh861/nCode/actions/workflows/ci.yml/badge.svg)](https://github.com/opsingh861/nCode/actions/workflows/ci.yml)
[![CodeQL](https://github.com/opsingh861/nCode/actions/workflows/codeql.yml/badge.svg)](https://github.com/opsingh861/nCode/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![Status](https://img.shields.io/badge/Status-Active-success)

**[📖 Documentation](https://opsingh861.github.io/nCode/)** · [Report a Bug](https://github.com/opsingh861/nCode/issues/new?template=bug_report.yml) · [Request a Feature](https://github.com/opsingh861/nCode/issues/new?template=feature_request.yml)

## Features

- Upload n8n workflow JSON and validate schema with Pydantic.
- Auto-transpile workflow nodes into runnable Python source.
- Detect runtime mode automatically:
  - **FastAPI mode** for webhook/chat triggers.
  - **Standalone script mode** for manual/schedule/no-trigger workflows.
- Generate downloadable ZIP project artifacts.
- Keep credentials secure using generated `os.getenv(...)` placeholders and `.env.example`.

## Supported Node Types

Status key:
- **Full**: concrete Python generation is implemented.
- **Partial**: generates code, but may include TODO/manual translation sections.
- **Stub**: placeholder TODO/pass-through output.

| Node Type | Status | Generated Code |
|---|---|---|
| `n8n-nodes-base.httpRequest` | Full | `requests.request(...)` with method/url, headers, query params, optional body, auth/env token fallback, JSON/text response handling |
| `n8n-nodes-base.httprequest` | Full | Alias of HTTP Request handler |
| `n8n-nodes-base.HttpRequest` | Full | Alias of HTTP Request handler |
| `n8n-nodes-base.set` | Full | Builds item JSON payload from assignments (manual mode) with raw mode fallback |
| `n8n-nodes-base.if` | Full | Condition expression generation with true/false branch item outputs |
| `n8n-nodes-base.code` | Partial | Passes through Python code if present; comments JS code with TODO for manual conversion |
| `n8n-nodes-base.merge` | Stub | TODO scaffold + pass-through items |
| `n8n-nodes-base.itemLists` | Stub | TODO scaffold + pass-through items |
| `n8n-nodes-base.itemlists` | Stub | Alias of Item Lists handler |
| `n8n-nodes-base.splitInBatches` | Stub | Alias to Item Lists stub handler |
| `n8n-nodes-base.splitinbatches` | Stub | Alias to Item Lists stub handler |
| `n8n-nodes-base.webhook` | Full | FastAPI route trigger scaffold (`@app.<method>("/<path>")`) with payload/query extraction |
| `n8n-nodes-base.scheduleTrigger` | Partial | Script entrypoint scaffold with schedule metadata comments |
| `n8n-nodes-base.scheduletrigger` | Partial | Alias of schedule trigger handler |
| `n8n-nodes-base.manualTrigger` | Partial | Script entrypoint scaffold (`run_workflow`) with initialized items |
| `n8n-nodes-base.manualtrigger` | Partial | Alias of manual trigger handler |
| `@n8n/n8n-nodes-langchain.chatTrigger` | Full | FastAPI chat route scaffold with message extraction |
| `@n8n/n8n-nodes-langchain.chattrigger` | Full | Alias of chat trigger handler |
| `n8n-nodes-base.postgres` | Stub | TODO scaffold with operation + credential env placeholder |
| `n8n-nodes-base.mySql` | Stub | TODO scaffold with operation + credential env placeholder |
| `n8n-nodes-base.mysql` | Stub | Alias of MySQL stub handler |
| `n8n-nodes-base.mongoDb` | Stub | TODO scaffold with operation + credential env placeholder |
| `n8n-nodes-base.mongodb` | Stub | Alias of MongoDB stub handler |
| `@n8n/n8n-nodes-langchain.openAi` | Stub | TODO scaffold for OpenAI model/operation |
| `@n8n/n8n-nodes-langchain.openai` | Stub | Alias of OpenAI stub handler |

Notes:
- Additional `@n8n/n8n-nodes-langchain.*` and AI-like types are routed to generic AI/LangChain fallback handlers.
- Unsupported node types are preserved as explicit TODO blocks so generated workflows remain runnable.

## Quick Start

```bash
cd n8n2py
python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Unix/macOS (bash/zsh):
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload
```

> Using a project-local virtual environment (like `.venv`) keeps dependencies isolated from your global Python installation and avoids version conflicts.

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/api/upload` | Upload n8n workflow JSON, transpile to Python, return preview + `download_id` |
| `GET` | `/api/download/{id}` | Download generated ZIP artifact for the given `download_id` |
| `GET` | `/api/supported-nodes` | List transpiler-supported node type strings |

### cURL examples

Upload a workflow:

```bash
curl -X POST "http://127.0.0.1:8000/api/upload" \
  -F "file=@workflow.json"
```

Download generated ZIP (replace with real ID from upload response):

```bash
curl -L "http://127.0.0.1:8000/api/download/<download_id>" -o workflow_python.zip
```

## Project Structure

```text
n8n2py/
├── .env.example
├── README.md
├── requirements.txt
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── __pycache__/
│   │   ├── __init__.cpython-314.pyc
│   │   └── main.cpython-314.pyc
│   └── transpiler/
│       ├── __init__.py
│       ├── core.py
│       ├── utils.py
│       ├── __pycache__/
│       │   ├── __init__.cpython-314.pyc
│       │   └── core.cpython-314.pyc
│       └── node_handlers/
│           ├── __init__.py
│           ├── ai_nodes.py
│           ├── data_nodes.py
│           ├── db_nodes.py
│           ├── http_nodes.py
│           ├── trigger_nodes.py
│           ├── utils.py
│           └── __pycache__/
│               ├── ai_nodes.cpython-314.pyc
│               ├── data_nodes.cpython-314.pyc
│               └── db_nodes.cpython-314.pyc
└── frontend/
    └── .gitkeep
```

## How It Works

Transpilation pipeline:

1. **Parse** incoming workflow JSON.
2. **Validate** payload against `N8nWorkflow`/`N8nNode` models.
3. **Build graph** from node definitions + n8n `connections`.
4. **Topological sort** execution order (cycle-safe).
5. **Detect mode** from trigger type (FastAPI route mode vs standalone script mode).
6. **Dispatch handlers** by node type through `HANDLER_MAP`.
7. **Generate Python** source with explicit `items` handoff between node outputs.
8. **Collect dependencies** and scaffold project artifacts.

## Generated Output

Each successful upload creates a downloadable ZIP containing:

- `main.py` — generated Python workflow runtime.
- `requirements.txt` — inferred package dependencies.
- `.env.example` — credential/env placeholders discovered from nodes.
- `README.md` — generated workflow-level quickstart notes.
- `workflow_meta.json` — metadata (`workflow_name`, `node_count`, generation timestamp).

## Security

- Credentials are not embedded as plaintext in generated code.
- Credential references are emitted as `os.getenv("...")` lookups.
- `.env.example` is generated to declare required variables without secrets.
- Upload/download flow uses strict validation (JSON-only upload, size limit, UUID download IDs).
- Temporary ZIP files are cleaned up after download and during lifecycle cleanup.

## Roadmap

- Build React frontend for upload/preview/download UX.
- Expand node handler coverage (especially AI and database nodes to full support).
- Add multi-language generators (JS/Go) through an abstract generator interface.
- Add automated tests for transpiler pipeline and API endpoints.

## License

MIT (placeholder)