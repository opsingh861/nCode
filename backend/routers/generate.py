"""FastAPI router: POST /api/generate and GET /api/supported-nodes (new)."""

from __future__ import annotations

from typing import Any

from backend.core.pipeline import PipelineResult, run_pipeline
from backend.handlers.registry import get_supported_types
from backend.models.response import GenerateResponse, NodePreview, PipelineWarning
from backend.models.workflow import N8nWorkflow
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

router = APIRouter()


@router.post("/api/generate", response_model=GenerateResponse)
async def generate_workflow(body: N8nWorkflow) -> GenerateResponse:
    """Transpile an n8n workflow JSON to Python.

    Accepts the raw n8n workflow JSON as the request body (application/json).
    Returns generated Python code, a requirements.txt, node preview, and warnings.
    """
    payload = body.model_dump()
    try:
        result: PipelineResult = run_pipeline(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}") from exc

    supported_set = set(get_supported_types())
    nodes_preview = [
        NodePreview(name=t, type=t, handled=(t.lower() in supported_set))
        for t in result.supported_nodes + result.unsupported_nodes
    ]
    warnings = [
        PipelineWarning(node_name="pipeline", message=w) for w in result.warnings
    ]

    return GenerateResponse(
        workflow_name=result.workflow_name,
        nodes_preview=nodes_preview,
        generated_code=result.generated_code,
        requirements_txt=result.requirements_txt,
        warnings=warnings,
        download_id=result.download_id,
    )


@router.get("/api/supported-nodes")
async def supported_nodes() -> dict[str, Any]:
    """Return all n8n node types the new pipeline can handle."""
    types = sorted(get_supported_types())
    return {"supported_types": types, "count": len(types)}
