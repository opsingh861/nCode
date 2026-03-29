"""Pydantic models for validating n8n workflow payloads and API responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class N8nNode(BaseModel):
    """Represents a single n8n workflow node."""

    id: str
    name: str
    type: str
    typeVersion: int | float
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
    """Represents the top-level n8n workflow JSON structure."""

    name: str = "Untitled Workflow"
    nodes: list[N8nNode]
    connections: dict[str, dict[str, list[list[N8nConnectionTarget]]]] = Field(
        default_factory=dict
    )
    settings: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def ensure_connections_present(cls, data: Any) -> Any:
        """Ensure missing/null `connections` is normalized to an empty dict."""
        if isinstance(data, dict):
            if "connections" not in data or data.get("connections") is None:
                data["connections"] = {}
        return data


class NodePreview(BaseModel):
    """Provides a lightweight node summary for frontend previews."""

    name: str
    type: str
    handled: bool


class UploadResponse(BaseModel):
    """Represents the API response after uploading an n8n workflow."""

    workflow_name: str
    nodes_preview: list[NodePreview]
    generated_code: str
    download_id: str
