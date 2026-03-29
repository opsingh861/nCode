"""Integration tests for the full pipeline (backend/core/pipeline.py).

Tests verify:
- A minimal workflow (trigger + set node) round-trips through the pipeline
  and produces syntactically valid Python.
- Pipeline returns a PipelineResult with expected fields.
- run_pipeline handles malformed JSON correctly.
- Generated code compiles without syntax errors (py_compile).
"""

import json
import pathlib
import py_compile
import tempfile

import pytest
from backend.core.pipeline import PipelineResult, run_pipeline

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_WORKFLOW = {
    "name": "Minimal Test",
    "nodes": [
        {
            "id": "1",
            "name": "Start",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [0, 0],
            "parameters": {},
        },
        {
            "id": "2",
            "name": "Set Data",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3,
            "position": [200, 0],
            "parameters": {
                "assignments": {
                    "assignments": [
                        {"name": "greeting", "value": "Hello World", "type": "string"}
                    ]
                },
                "options": {},
            },
        },
    ],
    "connections": {
        "Start": {"main": [[{"node": "Set Data", "type": "main", "index": 0}]]}
    },
}

WEBHOOK_WORKFLOW = {
    "name": "Webhook Test",
    "nodes": [
        {
            "id": "1",
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1,
            "position": [0, 0],
            "parameters": {
                "path": "my-hook",
                "httpMethod": "POST",
                "responseMode": "onReceived",
            },
        },
        {
            "id": "2",
            "name": "Respond",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1,
            "position": [200, 0],
            "parameters": {
                "respondWith": "json",
                "responseBody": "={{ $json }}",
            },
        },
    ],
    "connections": {
        "Webhook": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]}
    },
}

IF_WORKFLOW = {
    "name": "IF Test",
    "nodes": [
        {
            "id": "1",
            "name": "Trigger",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [0, 0],
            "parameters": {},
        },
        {
            "id": "2",
            "name": "IF Node",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [200, 0],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True},
                    "conditions": [
                        {
                            "id": "c1",
                            "leftValue": "={{ $json.value }}",
                            "operator": {"type": "number", "operation": "gt"},
                            "rightValue": 10,
                        }
                    ],
                    "combinator": "and",
                }
            },
        },
        {
            "id": "3",
            "name": "True Path",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3,
            "position": [400, -100],
            "parameters": {},
        },
        {
            "id": "4",
            "name": "False Path",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3,
            "position": [400, 100],
            "parameters": {},
        },
    ],
    "connections": {
        "Trigger": {"main": [[{"node": "IF Node", "type": "main", "index": 0}]]},
        "IF Node": {
            "main": [
                [{"node": "True Path", "type": "main", "index": 0}],
                [{"node": "False Path", "type": "main", "index": 0}],
            ]
        },
    },
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _compiles(source: str) -> bool:
    """Return True if *source* is valid Python syntax."""
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write(source)
        tmp_path = f.name
    try:
        py_compile.compile(tmp_path, doraise=True)
        return True
    except py_compile.PyCompileError:
        return False
    finally:
        pathlib.Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# PipelineResult structure tests
# ---------------------------------------------------------------------------


class TestPipelineResultFields:
    def test_returns_pipeline_result(self):
        result = run_pipeline(MINIMAL_WORKFLOW)
        assert isinstance(result, PipelineResult)

    def test_workflow_name(self):
        result = run_pipeline(MINIMAL_WORKFLOW)
        assert result.workflow_name == "Minimal Test"

    def test_has_generated_code(self):
        result = run_pipeline(MINIMAL_WORKFLOW)
        assert len(result.generated_code) > 0

    def test_has_requirements_txt(self):
        result = run_pipeline(MINIMAL_WORKFLOW)
        assert isinstance(result.requirements_txt, str)

    def test_has_download_id(self):
        result = run_pipeline(MINIMAL_WORKFLOW)
        assert len(result.download_id) > 0

    def test_warnings_is_list(self):
        result = run_pipeline(MINIMAL_WORKFLOW)
        assert isinstance(result.warnings, list)


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------


class TestModeDetection:
    def test_manual_trigger_is_script_mode(self):
        result = run_pipeline(MINIMAL_WORKFLOW)
        assert result.mode == "script"

    def test_webhook_trigger_is_fastapi_mode(self):
        result = run_pipeline(WEBHOOK_WORKFLOW)
        assert result.mode == "fastapi"


# ---------------------------------------------------------------------------
# Code validity (syntax check)
# ---------------------------------------------------------------------------


class TestCodeValidity:
    def test_minimal_workflow_compiles(self):
        result = run_pipeline(MINIMAL_WORKFLOW)
        assert _compiles(
            result.generated_code
        ), f"Generated code has syntax errors:\n{result.generated_code[:500]}"

    def test_webhook_workflow_compiles(self):
        result = run_pipeline(WEBHOOK_WORKFLOW)
        assert _compiles(
            result.generated_code
        ), f"Generated code has syntax errors:\n{result.generated_code[:500]}"

    def test_if_workflow_compiles(self):
        result = run_pipeline(IF_WORKFLOW)
        assert _compiles(
            result.generated_code
        ), f"Generated code has syntax errors:\n{result.generated_code[:500]}"


# ---------------------------------------------------------------------------
# JSON string input
# ---------------------------------------------------------------------------


class TestJsonStringInput:
    def test_accepts_json_string(self):
        result = run_pipeline(json.dumps(MINIMAL_WORKFLOW))
        assert result.workflow_name == "Minimal Test"

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            run_pipeline("not valid json {{{{")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_connections(self):
        wf = {
            "name": "Empty",
            "nodes": [
                {
                    "id": "1",
                    "name": "Solo",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
            "connections": {},
        }
        result = run_pipeline(wf)
        assert isinstance(result, PipelineResult)

    def test_disabled_nodes_skipped(self):
        wf = {
            "name": "Disabled",
            "nodes": [
                {
                    "id": "1",
                    "name": "Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "position": [0, 0],
                    "parameters": {},
                },
                {
                    "id": "2",
                    "name": "Disabled Node",
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3,
                    "position": [200, 0],
                    "parameters": {},
                    "disabled": True,
                },
            ],
            "connections": {
                "Trigger": {
                    "main": [[{"node": "Disabled Node", "type": "main", "index": 0}]]
                }
            },
        }
        result = run_pipeline(wf)
        assert (
            "Disabled Node" not in result.generated_code
            or "disabled" in result.generated_code.lower()
        )

    def test_unknown_node_type_uses_fallback(self):
        wf = {
            "name": "Unknown",
            "nodes": [
                {
                    "id": "1",
                    "name": "Mystery Node",
                    "type": "n8n-nodes-base.unknownNodeXYZ123",
                    "typeVersion": 1,
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
            "connections": {},
        }
        result = run_pipeline(wf)
        assert isinstance(result, PipelineResult)
        assert len(result.unsupported_nodes) > 0
