---
layout: home
title: Home
nav_order: 1
description: "nCode converts n8n workflow JSON into clean, production-ready Python — FastAPI routes or standalone scripts, automatically."
permalink: /
---

<p align="center">
  <img src="assets/logo/ncode-primary.png" alt="nCode" width="400" />
</p>

# nCode
{: .fs-9 }

Convert n8n workflows into clean, runnable Python — automatically.
{: .fs-6 .fw-300 }

[Get Started]({% link getting-started.md %}){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[View on GitHub](https://github.com/opsingh861/nCode){: .btn .fs-5 .mb-4 .mb-md-0 }

---

## What is nCode?

nCode is an open-source **transpiler** that converts [n8n](https://n8n.io) workflow JSON into clean, production-ready Python code. Upload your workflow and get back a complete project — Python source, `requirements.txt`, `.env.example`, and a ready-to-run `README.md` — all in a single ZIP download.

```
Upload workflow.json  →  Python project ZIP
         │                      │
         ▼                      ▼
  Pydantic validate      main.py (FastAPI or script)
  DAG build              requirements.txt
  Topo sort              .env.example
  Code emit              README.md
```

## Key Features

| Feature | Detail |
|---|---|
| **Dual output modes** | FastAPI routes for webhook/chat triggers; standalone `if __name__ == "__main__"` for manual/schedule triggers |
| **Expression engine** | Translates n8n `{{ }}` templates — `$json`, `$env`, `$now`, `$('Node').json`, `$fromAI()` — into idiomatic Python |
| **20+ node handlers** | HTTP requests, branching, data transforms, LangChain AI, databases, and more |
| **Credential safety** | All secrets emitted as `os.getenv(...)` with auto-generated `.env.example` |
| **Code quality gates** | Output is auto-formatted with `black` + `isort` and syntax-validated with `py_compile` |
| **Dependency inference** | `requirements.txt` is generated from the workflow — no manual package hunting |

## Quick Start

```bash
git clone https://github.com/opsingh861/nCode.git
cd nCode
pip install -r requirements.txt
uvicorn backend.main:app --reload
# Open http://localhost:8000
```

Or with Docker:

```bash
docker compose up --build
```

See the full [Getting Started]({% link getting-started.md %}) guide for detailed setup instructions.

## Project Status

[![CI](https://github.com/opsingh861/nCode/actions/workflows/ci.yml/badge.svg)](https://github.com/opsingh861/nCode/actions/workflows/ci.yml)
[![CodeQL](https://github.com/opsingh861/nCode/actions/workflows/codeql.yml/badge.svg)](https://github.com/opsingh861/nCode/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/opsingh861/nCode/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)

---

*Contributions welcome! See the [Contributing Guide]({% link contributing.md %}) to get started.*
