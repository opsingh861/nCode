"""Trigger node handlers.

Supported n8n node types:
- n8n-nodes-base.manualTrigger
- n8n-nodes-base.scheduleTrigger
- n8n-nodes-base.webhook
- n8n-nodes-base.executeWorkflowTrigger
- @n8n/n8n-nodes-langchain.chatTrigger
- n8n-nodes-base.errorTrigger (treated as trigger)
"""

from __future__ import annotations

import re

from backend.core.ir import IRNode, IRNodeKind
from backend.handlers.base import GenerationContext
from backend.handlers.registry import register
from backend.models.workflow import N8nNode


def _safe_var(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_") or "node"
    return f"n_{s}" if s[0].isdigit() else s


def _safe_path(raw: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9/_-]", "_", raw.strip().strip("/"))
    return cleaned or "webhook"


@register(
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.start",
)
class ManualTriggerHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        ctx.register_node_var(node.name, var)
        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=[
                f"# Manual trigger: {node.name!r}",
                f"{var}_output = [{{'json': {{}}}}]",
            ],
            comment="Manual / Script trigger — workflow starts here",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.manualTrigger", "n8n-nodes-base.start"]

    def required_packages(self) -> list[str]:
        return []


@register("n8n-nodes-base.executeWorkflowTrigger")
class ExecuteWorkflowTriggerHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        ctx.register_node_var(node.name, var)
        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=[
                f"# Execute Workflow Trigger: {node.name!r}",
                f"# items is passed in from the calling workflow",
                f"{var}_output = items if 'items' in dir() else [{{'json': {{}}}}]",
            ],
            comment="Execute Workflow trigger — receives items from parent workflow",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.executeWorkflowTrigger"]

    def required_packages(self) -> list[str]:
        return []


@register("n8n-nodes-base.scheduleTrigger")
class ScheduleTriggerHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        ctx.register_node_var(node.name, var)
        params = node.parameters

        rule = params.get("rule", {}) or {}
        interval_raw = rule.get("interval", [{}])
        interval = (
            interval_raw[0] if isinstance(interval_raw, list) and interval_raw else {}
        )

        field_val = interval.get("field", "hours")
        trigger_at_hour = interval.get("triggerAtHour", 0)
        trigger_at_minute = interval.get("triggerAtMinute", 0)
        interval_count = interval.get(
            "hoursInterval", interval.get("minutesInterval", 1)
        )

        if field_val == "cronExpression":
            cron_expr = interval.get("expression", "0 * * * *")
            code_lines = [
                "from apscheduler.schedulers.blocking import BlockingScheduler",
                "from apscheduler.triggers.cron import CronTrigger",
                "",
                "scheduler = BlockingScheduler()",
                "",
                "def workflow_job():",
                f"    pass  # TODO: insert workflow body here",
                "",
                f'scheduler.add_job(workflow_job, CronTrigger.from_crontab("{cron_expr}"))',
                f"{var}_output = [{{'json': {{'triggered': True}}}}]",
            ]
        elif field_val == "weeks":
            day = interval.get("triggerAtDay", [1])
            day_val = day[0] if isinstance(day, list) and day else day
            code_lines = [
                "from apscheduler.schedulers.blocking import BlockingScheduler",
                "",
                "scheduler = BlockingScheduler()",
                "# Weekly trigger",
                "def workflow_job():",
                f"    pass  # TODO: insert workflow body here",
                "",
                f"scheduler.add_job(workflow_job, 'cron', day_of_week={day_val!r}, hour={trigger_at_hour}, minute={trigger_at_minute})",
                f"{var}_output = [{{'json': {{'triggered': True}}}}]",
            ]
        elif field_val == "days":
            code_lines = [
                "from apscheduler.schedulers.blocking import BlockingScheduler",
                "",
                "scheduler = BlockingScheduler()",
                "def workflow_job():",
                f"    pass  # TODO: insert workflow body here",
                "",
                f"scheduler.add_job(workflow_job, 'cron', hour={trigger_at_hour}, minute={trigger_at_minute})",
                f"{var}_output = [{{'json': {{'triggered': True}}}}]",
            ]
        elif field_val == "minutes":
            code_lines = [
                "from apscheduler.schedulers.blocking import BlockingScheduler",
                "",
                "scheduler = BlockingScheduler()",
                "def workflow_job():",
                f"    pass  # TODO: insert workflow body here",
                "",
                f"scheduler.add_job(workflow_job, 'interval', minutes={interval_count})",
                f"{var}_output = [{{'json': {{'triggered': True}}}}]",
            ]
        else:  # hours (default)
            code_lines = [
                "from apscheduler.schedulers.blocking import BlockingScheduler",
                "",
                "scheduler = BlockingScheduler()",
                "def workflow_job():",
                f"    pass  # TODO: insert workflow body here",
                "",
                f"scheduler.add_job(workflow_job, 'interval', hours={interval_count})",
                f"{var}_output = [{{'json': {{'triggered': True}}}}]",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["from apscheduler.schedulers.blocking import BlockingScheduler"],
            pip_packages=["apscheduler"],
            code_lines=code_lines,
            comment=f"Schedule trigger: {node.name!r}",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.scheduleTrigger"]

    def required_packages(self) -> list[str]:
        return ["apscheduler"]


@register("n8n-nodes-base.webhook")
class WebhookTriggerHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        ctx.register_node_var(node.name, var)
        params = node.parameters

        method_raw = str(params.get("httpMethod", "POST")).strip().upper()
        method = (
            method_raw.lower()
            if method_raw.lower() in {"get", "post", "put", "patch", "delete"}
            else "post"
        )
        path_raw = str(params.get("path", "") or _safe_var(node.name))
        path = _safe_path(path_raw)

        code_lines = [
            f'@app.{method}("/{path}")',
            "async def workflow_endpoint(request: Request) -> JSONResponse:",
            "    load_dotenv()",
            "    query_params = dict(request.query_params)",
            "    headers = dict(request.headers)",
        ]

        if method == "get":
            code_lines += [
                f"    {var}_output = [{{'json': {{'query': query_params, 'headers': headers}}}}]",
            ]
        else:
            code_lines += [
                "    try:",
                "        payload = await request.json()",
                "    except Exception:",
                "        payload = {}",
                f"    {var}_output = [{{'json': {{'body': payload, 'query': query_params, 'headers': headers}}}}]",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=[
                "from fastapi import FastAPI, Request",
                "from fastapi.responses import JSONResponse",
                "from dotenv import load_dotenv",
            ],
            pip_packages=["fastapi", "uvicorn", "python-dotenv"],
            code_lines=code_lines,
            comment=f"Webhook trigger: {method.upper()} /{path}",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.webhook"]

    def required_packages(self) -> list[str]:
        return ["fastapi", "uvicorn"]


@register("@n8n/n8n-nodes-langchain.chatTrigger")
class ChatTriggerHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        ctx.register_node_var(node.name, var)
        params = node.parameters
        path = _safe_path(str(params.get("path", "chat")))

        code_lines = [
            "class ChatRequest(BaseModel):",
            "    message: str | None = None",
            "    text: str | None = None",
            "    input: str | None = None",
            "    sessionId: str | None = None",
            "",
            f'@app.post("/{path}")',
            "async def chat_endpoint(body: ChatRequest) -> JSONResponse:",
            "    load_dotenv()",
            "    payload = body.model_dump(exclude_none=True)",
            '    message = body.message or body.text or body.input or ""',
            '    session_id = body.sessionId or ""',
            f"    {var}_output = [{{'json': {{'message': message, 'sessionId': session_id, 'body': payload}}}}]",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=[
                "from fastapi import FastAPI",
                "from fastapi.responses import JSONResponse",
                "from pydantic import BaseModel",
                "from dotenv import load_dotenv",
            ],
            pip_packages=["fastapi", "uvicorn", "python-dotenv"],
            code_lines=code_lines,
            comment=f"Chat trigger endpoint: POST /{path}",
        )

    def supported_operations(self) -> list[str]:
        return ["@n8n/n8n-nodes-langchain.chatTrigger"]

    def required_packages(self) -> list[str]:
        return ["fastapi", "uvicorn"]


def is_trigger_node(node_type: str) -> bool:
    """Return True if the given node type is a workflow trigger."""
    lowered = node_type.lower()
    trigger_keys = {
        "n8n-nodes-base.manualtrigger",
        "n8n-nodes-base.start",
        "n8n-nodes-base.scheduletrigger",
        "n8n-nodes-base.webhook",
        "n8n-nodes-base.errortrigger",
        "n8n-nodes-base.executeworkflowtrigger",
        "@n8n/n8n-nodes-langchain.chattrigger",
    }
    return lowered in trigger_keys


def is_fastapi_trigger(node_type: str) -> bool:
    """Return True for triggers that require FastAPI routing mode."""
    lowered = node_type.lower()
    return lowered in {
        "n8n-nodes-base.webhook",
        "@n8n/n8n-nodes-langchain.chattrigger",
    }
