---
layout: default
title: Node Handlers
nav_order: 4
description: "Complete reference of supported n8n node types and their generated Python output."
---

# Node Handlers
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Status Legend

| Status | Meaning |
|---|---|
| ✅ **Full** | Concrete Python generated — no manual editing required for standard use |
| ⚠️ **Partial** | Code generated, but some paths include `# TODO` comments for edge cases |
| 🔧 **Stub** | Scaffold with explicit TODO — requires manual completion |

---

## Triggers

Trigger nodes control the **output mode** of the entire generated file.

| Node type | Status | Output |
|---|---|---|
| `n8n-nodes-base.manualTrigger` | ⚠️ Partial | `def run_workflow():` + `if __name__ == "__main__"` |
| `n8n-nodes-base.scheduleTrigger` | ⚠️ Partial | Same as manual trigger with schedule metadata comments |
| `n8n-nodes-base.webhook` | ✅ Full | `@app.post("/path")` FastAPI route with Pydantic request model |
| `@n8n/n8n-nodes-langchain.chatTrigger` | ✅ Full | `@app.post("/chat")` FastAPI route with message extraction |

**Note:** Multiple trigger aliases (`manualTrigger` / `manualtrigger`, etc.) are registered identically.

---

## HTTP

| Node type | Status | Generated construct |
|---|---|---|
| `n8n-nodes-base.httpRequest` | ✅ Full | `requests.request(method, url, headers=..., params=..., json=..., auth=...)` |

**Features:**
- All HTTP methods (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`)
- Query parameters and custom headers
- JSON and form body support
- Bearer token / Basic auth with `os.getenv()` credential placeholders
- Response body parsed as JSON with text fallback

---

## Flow Control

| Node type | Status | Generated construct |
|---|---|---|
| `n8n-nodes-base.if` | ✅ Full | `if condition: ... else: ...` with branch item lists |
| `n8n-nodes-base.switch` | 🔧 Stub | Multi-branch scaffold with TODO |
| `n8n-nodes-base.merge` | 🔧 Stub | TODO pass-through |
| `n8n-nodes-base.splitInBatches` | 🔧 Stub | TODO scaffold |

The IF handler integrates with the **expression engine** to translate n8n conditions into Python boolean expressions, and uses post-dominator analysis to correctly scope the merge point after branches.

---

## Data Transform

| Node type | Status | Generated construct |
|---|---|---|
| `n8n-nodes-base.set` | ✅ Full | Builds `{"json": {...}}` items from field assignments; supports raw mode |
| `n8n-nodes-base.filter` | ⚠️ Partial | List comprehension with translated condition expression |
| `n8n-nodes-base.itemLists` | 🔧 Stub | TODO scaffold |
| `n8n-nodes-base.code` | ⚠️ Partial | Python code blocks passed through; JS blocks commented with TODO |

---

## Databases

All database handlers are currently **stubs** that scaffold the operation and credential environment variables. They are valid Python — they just need the implementation filled in.

| Node type | Generated packages |
|---|---|
| `n8n-nodes-base.postgres` | `psycopg2-binary` |
| `n8n-nodes-base.mySql` | `pymysql` |
| `n8n-nodes-base.mongoDb` | `pymongo` |

---

## Apps & SaaS

All app handlers are currently **stubs**.

| Node type | Generated packages |
|---|---|
| `n8n-nodes-base.slack` | `slack-sdk` |
| `n8n-nodes-base.notion` | `notion-client` |
| `n8n-nodes-base.airtable` | `pyairtable` |
| `n8n-nodes-base.googleSheets` | `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` |

---

## AI & LangChain

| Node type | Status | Generated construct |
|---|---|---|
| `@n8n/n8n-nodes-langchain.openAi` | 🔧 Stub | TODO with model/operation metadata |
| `@n8n/n8n-nodes-langchain.lmChatOpenAi` | ⚠️ Partial | `ChatOpenAI(model=..., temperature=...)` instantiation |
| `@n8n/n8n-nodes-langchain.agent` | ⚠️ Partial | LangChain `AgentExecutor` scaffold with composed tools and memory |
| `@n8n/n8n-nodes-langchain.memoryBufferWindow` | ⚠️ Partial | `ConversationBufferWindowMemory` — requires `langchain-classic` |
| Other `@n8n/n8n-nodes-langchain.*` | 🔧 Stub | Generic LangChain TODO scaffold |

**LangChain packages:** When any `ConversationBuffer*Memory` node is detected, both `langchain` **and** `langchain-classic` are added to `requirements.txt`.

---

## Fallback Handler

Any unrecognised node type is handled by the **fallback handler**, which emits:

```python
# TODO: Unsupported node type 'n8n-nodes-base.xyzNode'
# Node: "My Node Name"
n_my_node_name_output = previous_output  # pass-through
```

This keeps the generated workflow runnable while clearly marking the gap. Contributions to implement these nodes are welcome — see [Contributing]({% link contributing.md %}).

---

## Requesting a New Handler

Open a [Node Handler Request](https://github.com/opsingh861/nCode/issues/new?template=node_handler_request.yml) on GitHub.
