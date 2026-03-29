---
layout: default
title: Getting Started
nav_order: 2
description: "Install and run nCode locally or with Docker."
---

# Getting Started
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| Docker (optional) | 24+ |

---

## Option 1 — Local development

### 1. Clone the repository

```bash
git clone https://github.com/opsingh861/nCode.git
cd nCode
```

### 2. Backend setup

```bash
cd backend
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r ../requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env if you need custom settings (all values have safe defaults)
```

### 4. Start the backend

```bash
# From the repo root
uvicorn backend.main:app --reload --port 8000
```

The OpenAPI docs are available at `http://localhost:8000/docs`.

### 5. Frontend setup (optional)

The frontend is a React + Vite app that proxies API calls to `:8000`.

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## Option 2 — Docker Compose (recommended for production testing)

Starts the FastAPI backend and the Nginx-served React frontend together:

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | `http://localhost:3000` |
| Backend API | `http://localhost:8000` |
| API docs | `http://localhost:8000/docs` |

---

## Using nCode

### Upload a workflow

1. Open the UI (or use the API directly).
2. Drag-and-drop or browse to your `workflow.json` export from n8n.
3. Click **Generate**.
4. Preview the generated Python code in the right panel.
5. Click **Download ZIP** to get the full project artifact.

### Generated ZIP structure

```text
workflow_<name>/
├── main.py             # Generated Python workflow
├── requirements.txt    # Inferred package dependencies
├── .env.example        # Credential placeholder template
└── README.md           # Quickstart notes for the generated workflow
```

### API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/api/upload` | Upload workflow JSON → returns code preview + `download_id` |
| `GET` | `/api/download/{id}` | Download ZIP artifact |
| `GET` | `/api/supported-nodes` | Lists all registered node type strings |

```bash
# Upload
curl -X POST http://localhost:8000/api/upload -F "file=@workflow.json"

# Download (replace <id> with the download_id from the response)
curl -L http://localhost:8000/api/download/<id> -o workflow.zip
```

---

## Running Tests

```bash
# Activate the backend venv, then from the repo root:
backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v
```

All four test modules run in a few seconds and require no external services.

---

## Next Steps

- Read the [Architecture]({% link architecture.md %}) page to understand the transpiler pipeline.
- Browse [Node Handlers]({% link node-handlers.md %}) to see which n8n nodes are supported.
- Check out [Contributing]({% link contributing.md %}) to submit a new handler or bug fix.
