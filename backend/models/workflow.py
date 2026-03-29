"""Pydantic models for validating n8n workflow payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class N8nNode(BaseModel):
    """Represents a single n8n workflow node."""

    id: str = ""
    name: str
    type: str
    typeVersion: int | float = 1
    parameters: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] | None = None
    position: list[int] = Field(default_factory=lambda: [0, 0])
    disabled: bool | None = None
    notes: str | None = None


class N8nConnectionTarget(BaseModel):
    """Represents a target node reference in n8n connection graphs."""

    node: str
    type: str = "main"
    index: int = 0


class N8nWorkflow(BaseModel):
    """Represents the top-level n8n workflow JSON structure.

    The ``connections`` field maps:
        source_node_name -> connection_type -> list[list[N8nConnectionTarget]]

    Supported connection types include:
        - "main"             — standard execution flow
        - "ai_tool"          — tool attached to an AI agent
        - "ai_memory"        — memory backend for AI node
        - "ai_languageModel" — LLM model for AI node
        - "ai_outputParser"  — output parser for LLM chain
        - "ai_retriever"     — retriever for RAG chains
        - "ai_document"      — document loader
        - "ai_embedding"     — embedding model
        - "ai_textSplitter"  — text splitter
        - "ai_vectorStore"   — vector store
    """

    name: str = "Untitled Workflow"
    nodes: list[N8nNode]
    connections: dict[str, dict[str, list[list[N8nConnectionTarget]]]] = Field(
        default_factory=dict
    )
    settings: dict[str, Any] | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Sample Workflow",
                "nodes": [
                    {
                        "id": "1",
                        "name": "Manual Trigger",
                        "type": "n8n-nodes-base.manualTrigger",
                        "typeVersion": 1,
                        "position": [240, 300],
                        "parameters": {},
                    },
                    {
                        "id": "2",
                        "name": "Set",
                        "type": "n8n-nodes-base.set",
                        "typeVersion": 3,
                        "position": [460, 300],
                        "parameters": {
                            "values": {
                                "string": [{"name": "message", "value": "hello"}]
                            }
                        },
                    },
                ],
                "connections": {
                    "Manual Trigger": {
                        "main": [[{"node": "Set", "type": "main", "index": 0}]]
                    }
                },
                "settings": {},
            }
        }
    }

    @model_validator(mode="before")
    @classmethod
    def normalize_connections(cls, data: Any) -> Any:
        """Normalize missing/null connections and handle all connection type keys."""
        if not isinstance(data, dict):
            return data

        raw_connections = data.get("connections")
        if not raw_connections:
            data["connections"] = {}
            return data

        normalized: dict[str, dict[str, list[list[dict]]]] = {}
        for source_name, conn_types in raw_connections.items():
            if not isinstance(conn_types, dict):
                continue
            normalized[source_name] = {}
            for conn_type, outputs in conn_types.items():
                if not isinstance(outputs, list):
                    continue
                normalized_outputs: list[list[dict]] = []
                for branch in outputs:
                    if not isinstance(branch, list):
                        normalized_outputs.append([])
                        continue
                    normalized_branch: list[dict] = []
                    for target in branch:
                        if target is None:
                            continue
                        if isinstance(target, dict):
                            normalized_branch.append(target)
                        else:
                            normalized_branch.append(target)
                    normalized_outputs.append(normalized_branch)
                normalized[source_name][conn_type] = normalized_outputs

        data["connections"] = normalized
        return data
