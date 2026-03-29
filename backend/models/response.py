"""API response models for the n8n-to-Python transpiler."""

from __future__ import annotations

from pydantic import BaseModel


class NodePreview(BaseModel):
    """Lightweight node summary for frontend display."""

    name: str
    type: str
    handled: bool


class PipelineWarning(BaseModel):
    """A warning produced during the transpilation pipeline."""

    node_name: str | None = None
    message: str


class GenerateResponse(BaseModel):
    """Full response returned by the /api/generate endpoint."""

    workflow_name: str
    nodes_preview: list[NodePreview]
    generated_code: str
    requirements_txt: str
    warnings: list[PipelineWarning]
    download_id: str
