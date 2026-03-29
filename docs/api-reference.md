---
layout: default
title: API Reference
nav_order: 5
description: "REST API endpoints exposed by the nCode FastAPI backend."
---

# API Reference
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

The nCode backend is a **FastAPI** application. Interactive Swagger UI is available at `http://localhost:8000/docs` when running locally.

---

## Base URL

| Environment | Base URL |
|---|---|
| Local development | `http://localhost:8000` |
| Docker Compose | `http://localhost:8000` |

---

## Endpoints

### Health check

```
GET /
```

Returns `{"status": "ok"}` to confirm the service is running.

**Response `200 OK`**
```json
{
  "status": "ok"
}
```

---

### Upload workflow

```
POST /api/upload
Content-Type: multipart/form-data
```

Uploads an n8n workflow JSON file, runs the transpiler pipeline, and returns the generated Python code preview.

**Request**

| Field | Type | Description |
|---|---|---|
| `file` | `file` (multipart) | The n8n workflow JSON export |

**Response `200 OK`**
```json
{
  "workflow_name": "My Workflow",
  "generated_code": "import os\nimport requests\n...",
  "requirements_txt": "requests==2.31.0\n...",
  "download_id": "550e8400-e29b-41d4-a716-446655440000",
  "warnings": [],
  "mode": "script"
}
```

| Field | Type | Description |
|---|---|---|
| `workflow_name` | `string` | Workflow name from the JSON |
| `generated_code` | `string` | Full generated `main.py` source |
| `requirements_txt` | `string` | Inferred `requirements.txt` content |
| `download_id` | `string` (UUID4) | Token to retrieve the ZIP artifact |
| `warnings` | `string[]` | Non-fatal issues from transpilation |
| `mode` | `"script"` \| `"fastapi"` | Detected output mode |

**Error responses**

| Status | Reason |
|---|---|
| `400` | Invalid JSON, missing required fields, or Pydantic validation failure |
| `422` | Malformed multipart request |
| `500` | Unexpected transpiler error |

**cURL example**
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@my_workflow.json"
```

---

### Download ZIP

```
GET /api/download/{download_id}
```

Streams the generated project ZIP for the given `download_id`.

**Path parameter**

| Parameter | Type | Description |
|---|---|---|
| `download_id` | `string` (UUID4) | The `download_id` from the upload response |

**Response `200 OK`**

`Content-Type: application/zip` — binary ZIP file download.

The ZIP contains:

```text
<workflow_name>/
├── main.py
├── requirements.txt
├── .env.example
└── README.md
```

**Error responses**

| Status | Reason |
|---|---|
| `404` | `download_id` not found or expired |

**cURL example**
```bash
curl -L http://localhost:8000/api/download/550e8400-e29b-41d4-a716-446655440000 \
  -o workflow.zip
```

---

### List supported nodes

```
GET /api/supported-nodes
```

Returns all n8n node type strings that have a registered handler.

**Response `200 OK`**
```json
{
  "supported_nodes": [
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.set",
    "n8n-nodes-base.if",
    "n8n-nodes-base.webhook",
    "..."
  ]
}
```

---

## OpenAPI / Swagger

The full OpenAPI 3.1 specification is served at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **JSON spec**: `http://localhost:8000/openapi.json`
