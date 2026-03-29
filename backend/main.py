"""FastAPI application for uploading n8n workflows and downloading transpiled Python projects.

This module provides a production-focused API surface for the nCode backend:

- `GET /` health probe.
- `POST /api/upload` for n8n JSON upload, validation, transpilation, and ZIP packaging.
- `GET /api/download/{download_id}` for one-time ZIP download with secure ID validation.
- `GET /api/supported-nodes` for transpiler capability introspection.

Design goals implemented here:

- Modern FastAPI lifecycle with `lifespan` context manager.
- Environment-driven configuration loaded from `.env`.
- Strict upload validation (file type, size, JSON format, schema).
- Safe file handling and path traversal protections.
- Deterministic artifact generation and metadata capture.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.background import BackgroundTask

from backend.models import GenerateResponse, N8nWorkflow, NodePreview, PipelineWarning
from backend.core.pipeline import run_pipeline
from backend.routers.generate import router as generate_router

# Load environment variables as early as possible so configuration values are
# available during app creation and runtime entrypoint execution.
load_dotenv()

# Strict UUID format check to prevent path traversal and non-opaque IDs.
UUID_REGEX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def _read_int_env(var_name: str, default: int) -> int:
    """Read an integer env var safely, returning a positive fallback on errors."""
    raw_value = os.getenv(var_name)
    if raw_value is None:
        return default

    try:
        parsed = int(raw_value)
    except ValueError:
        return default

    return parsed if parsed > 0 else default


TEMP_DIR = Path(os.getenv("TEMP_DIR", "./tmp")).resolve()
MAX_UPLOAD_SIZE_MB = _read_int_env("MAX_UPLOAD_SIZE_MB", 10)
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _sanitize_filename(value: str) -> str:
    """Sanitize arbitrary text into a cross-platform safe filename stem."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "workflow"


def _validate_download_id(download_id: str) -> str:
    """Validate UUID format and normalize to canonical lowercase string."""
    if not UUID_REGEX.fullmatch(download_id):
        raise HTTPException(status_code=400, detail="Invalid download_id format")

    try:
        parsed_uuid = uuid.UUID(download_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid download_id format") from exc

    return str(parsed_uuid)


# ---------------------------------------------------------------------------
# Project artifact generators (README, Dockerfile, etc.)
# ---------------------------------------------------------------------------

def _generate_readme(workflow_name: str, nodes: list, is_fastapi_mode: bool = False) -> str:
    mode = "FastAPI web service" if is_fastapi_mode else "standalone script"
    node_list = "\n".join(f"- {n.name} ({n.type})" for n in nodes)
    return (
        f"# {workflow_name}\n\n"
        f"Auto-generated Python project from n8n workflow.\n\n"
        f"**Mode:** {mode}\n\n"
        f"## Nodes\n\n{node_list}\n\n"
        f"## Setup\n\n"
        f"```bash\n"
        f"python -m venv .venv\n"
        f"# Windows (PowerShell): .\\.venv\\Scripts\\Activate.ps1\n"
        f"# Unix/macOS: source .venv/bin/activate\n"
        f"pip install -r requirements.txt\n"
        f"cp .env.example .env\n"
        + f"({f'uvicorn main:app --reload' if is_fastapi_mode else 'python main.py'})\n"
        f"```\n\n"
        f"> Using a local virtual environment (`.venv`) keeps dependencies isolated from global Python packages and avoids version conflicts.\n"
    )


def _generate_dockerfile(is_fastapi_mode: bool = False) -> str:
    cmd = 'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]' if is_fastapi_mode else 'CMD ["python", "main.py"]'
    return (
        "FROM python:3.11-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY . .\n"
        f"{cmd}\n"
    )


def _generate_dockerignore() -> str:
    return "__pycache__/\n*.pyc\n.env\n.venv/\n"


def _generate_env_example(workflow_dict: dict) -> str:
    return (
        "# Environment variables for this workflow\n"
        "# Copy to .env and fill in values\n\n"
        "# OPENAI_API_KEY=sk-...\n"
        "# ANTHROPIC_API_KEY=sk-ant-...\n"
        "# POSTGRES_HOST=localhost\n"
        "# REDIS_HOST=localhost\n"
    )


def _cleanup_expired_temp_files(temp_dir: Path, max_age_seconds: int = 3600) -> None:
    """Delete files older than the provided age threshold from the temp directory."""
    if not temp_dir.exists() or not temp_dir.is_dir():
        return

    now = time.time()
    for child in temp_dir.iterdir():
        if not child.is_file():
            continue

        try:
            file_age = now - child.stat().st_mtime
            if file_age > max_age_seconds:
                child.unlink(missing_ok=True)
        except OSError:
            # Cleanup should be best-effort and must not break shutdown.
            continue


def _get_upload_size_bytes(upload_file: UploadFile) -> int:
    """Get upload size without reading the full body into memory.

    FastAPI's `UploadFile` wraps a spooled temporary file object. We rely on
    seek/tell operations to inspect length and then rewind to original position.
    """
    current_position = upload_file.file.tell()
    upload_file.file.seek(0, os.SEEK_END)
    size_bytes = upload_file.file.tell()
    upload_file.file.seek(current_position)
    return size_bytes


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manage startup/shutdown lifecycle resources.

    Startup:
    - Ensure temp directory exists.

    Shutdown:
    - Remove stale temp files older than one hour.
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    yield
    _cleanup_expired_temp_files(TEMP_DIR, max_age_seconds=3600)


app = FastAPI(title="nCode API", version="2.0.0", lifespan=lifespan)

# Development-friendly CORS policy for browser integration.
# This is intentionally permissive and can be tightened later through env config.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the new pipeline router (provides /api/generate and /api/supported-nodes).
app.include_router(generate_router)


@app.get("/")
async def health_check() -> dict[str, str]:
    """Health endpoint used by clients and container probes."""
    return {"status": "ok", "service": "nCode"}


@app.post("/api/upload", response_model=GenerateResponse)
async def upload_workflow(file: UploadFile = File(...)) -> GenerateResponse:
    """Validate an n8n workflow upload, transpile it, and package output files.

    The endpoint performs strict validation in the following order:
    1) Ensure the upload is a JSON file by extension.
    2) Enforce max upload size before reading full content.
    3) Parse JSON payload.
    4) Validate payload schema with `N8nWorkflow`.
    5) Run pipeline to transpile and generate project artifacts.
    6) Store artifacts in a downloadable ZIP under a UUID-based identifier.
    """
    original_filename = file.filename or "workflow.json"
    if not original_filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are allowed")

    try:
        size_bytes = _get_upload_size_bytes(file)
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Unable to inspect uploaded file size") from exc

    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds max upload size of {MAX_UPLOAD_SIZE_MB} MB",
        )

    # Safe to read entire file content now that size was validated.
    raw_content = await file.read()

    try:
        workflow_dict: dict[str, Any] = json.loads(raw_content.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Uploaded file must be UTF-8 encoded JSON") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc.msg}") from exc

    try:
        workflow = N8nWorkflow.model_validate(workflow_dict)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    try:
        result = run_pipeline(workflow_dict)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Transpilation failed: {exc}") from exc

    generated_code = result.generated_code
    requirements_content = result.requirements_txt or ""

    _is_fastapi = result.mode == "fastapi"
    readme_content = _generate_readme(workflow.name, workflow.nodes, is_fastapi_mode=_is_fastapi)
    dockerfile_content = _generate_dockerfile(is_fastapi_mode=_is_fastapi)
    dockerignore_content = _generate_dockerignore()
    env_example_content = _generate_env_example(workflow_dict)

    download_id = result.download_id
    zip_path = TEMP_DIR / f"{download_id}.zip"

    workflow_meta = {
        "workflow_name": workflow.name,
        "node_count": len(workflow.nodes),
        "generated_at": datetime.now(UTC).isoformat(),
    }

    with ZipFile(zip_path, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("main.py", generated_code)
        archive.writestr("requirements.txt", requirements_content)
        archive.writestr(".env.example", env_example_content)
        archive.writestr("README.md", readme_content)
        archive.writestr("Dockerfile", dockerfile_content)
        archive.writestr(".dockerignore", dockerignore_content)
        archive.writestr("workflow_meta.json", json.dumps(workflow_meta, indent=2))

    from backend.handlers.registry import get_supported_types
    supported_set = set(get_supported_types())
    nodes_preview = [
        NodePreview(name=node.name, type=node.type, handled=(node.type.lower() in supported_set))
        for node in workflow.nodes
    ]
    warnings = [PipelineWarning(node_name="pipeline", message=w) for w in result.warnings]

    return GenerateResponse(
        workflow_name=workflow.name,
        nodes_preview=nodes_preview,
        generated_code=generated_code,
        requirements_txt=requirements_content,
        warnings=warnings,
        download_id=download_id,
    )


@app.get("/api/download/{download_id}")
async def download_generated_zip(download_id: str) -> FileResponse:
    """Download previously generated ZIP by secure UUID identifier.

    Security notes:
    - `download_id` is constrained to a UUID regex and parsed via `uuid.UUID`.
    - Server path is constructed from validated ID only.
    - File is deleted after successful response handling via `BackgroundTask`.
    """
    normalized_id = _validate_download_id(download_id)
    zip_path = TEMP_DIR / f"{normalized_id}.zip"

    if not zip_path.exists() or not zip_path.is_file():
        raise HTTPException(status_code=404, detail="Download not found")

    workflow_name = "workflow"
    try:
        with ZipFile(zip_path, mode="r") as archive:
            with archive.open("workflow_meta.json") as meta_file:
                metadata = json.loads(meta_file.read().decode("utf-8"))
                workflow_name = str(metadata.get("workflow_name") or workflow_name)
    except Exception:
        # Filename fallback keeps download functional even if metadata is missing/corrupt.
        workflow_name = "workflow"

    download_filename = f"{_sanitize_filename(workflow_name)}_python.zip"

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=download_filename,
        background=BackgroundTask(lambda: zip_path.unlink(missing_ok=True)),
    )




if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=_read_int_env("PORT", 8000),
        reload=True,
    )
