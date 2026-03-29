"""Tests for individual node handlers."""

import pytest

from backend.core.expression_engine import VariableContext
from backend.core.ir import IRNodeKind
from backend.handlers.ai_langchain import (
    AiAgentHandler,
    BasicLlmChainHandler,
    SentimentAnalysisHandler,
)
from backend.handlers.base import GenerationContext
from backend.handlers.data_transform import FilterNodeHandler, SetNodeHandler
from backend.handlers.fallback import FALLBACK
from backend.handlers.flow_control import IfNodeHandler, NoOpHandler
from backend.handlers.http import HttpRequestHandler
from backend.handlers.triggers import (
    ChatTriggerHandler,
    ManualTriggerHandler,
    ScheduleTriggerHandler,
    WebhookTriggerHandler,
)
from backend.models.workflow import N8nNode


def _make_node(name: str, node_type: str, params: dict = None) -> N8nNode:
    return N8nNode(
        id=name.lower().replace(" ", "_"),
        name=name,
        type=node_type,
        typeVersion=1,
        position=[0, 0],
        parameters=params or {},
    )


def _make_ctx(mode: str = "script") -> GenerationContext:
    ctx = GenerationContext(mode=mode)
    ctx.var_context.register("Prev", "prev")
    return ctx


# ---------------------------------------------------------------------------
# ManualTriggerHandler
# ---------------------------------------------------------------------------


class TestManualTriggerHandler:
    def test_generates_statement(self):
        h = ManualTriggerHandler()
        node = _make_node("Start", "n8n-nodes-base.manualTrigger")
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        assert ir.kind == IRNodeKind.STATEMENT
        assert ir.python_var

    def test_output_variable_registered(self):
        h = ManualTriggerHandler()
        node = _make_node("Start", "n8n-nodes-base.manualTrigger")
        ctx = _make_ctx()
        h.generate(node, ctx)
        assert ctx.var_context.resolve("Start") != ctx.var_context.resolve(
            "__unknown__"
        )

    def test_code_lines_not_empty(self):
        h = ManualTriggerHandler()
        node = _make_node("Start", "n8n-nodes-base.manualTrigger")
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        assert len(ir.code_lines) > 0

    def test_output_var_is_list(self):
        h = ManualTriggerHandler()
        node = _make_node("Start", "n8n-nodes-base.manualTrigger")
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        assert "_output" in code


# ---------------------------------------------------------------------------
# WebhookTriggerHandler
# ---------------------------------------------------------------------------


class TestWebhookTriggerHandler:
    def test_fastapi_mode_generates_route(self):
        h = WebhookTriggerHandler()
        node = _make_node(
            "Webhook",
            "n8n-nodes-base.webhook",
            {
                "path": "my-hook",
                "httpMethod": "POST",
            },
        )
        ctx = _make_ctx(mode="fastapi")
        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        assert "@app." in code or "app." in code

    def test_path_in_code(self):
        h = WebhookTriggerHandler()
        node = _make_node(
            "Webhook",
            "n8n-nodes-base.webhook",
            {
                "path": "custom-path",
                "httpMethod": "GET",
            },
        )
        ctx = _make_ctx(mode="fastapi")
        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        assert "custom-path" in code


# ---------------------------------------------------------------------------
# ChatTriggerHandler
# ---------------------------------------------------------------------------


class TestChatTriggerHandler:
    def test_generates_typed_body_model(self):
        h = ChatTriggerHandler()
        node = _make_node(
            "When chat message received",
            "@n8n/n8n-nodes-langchain.chatTrigger",
            {
                "path": "chat",
            },
        )
        ctx = _make_ctx(mode="fastapi")
        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)

        assert "class ChatRequest(BaseModel):" in code
        assert "async def chat_endpoint(body: ChatRequest) -> JSONResponse:" in code


# ---------------------------------------------------------------------------
# HttpRequestHandler
# ---------------------------------------------------------------------------


class TestHttpRequestHandler:
    def test_get_request(self):
        h = HttpRequestHandler()
        node = _make_node(
            "HTTP",
            "n8n-nodes-base.httpRequest",
            {
                "method": "GET",
                "url": "https://api.example.com/data",
            },
        )
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        assert "requests" in code or "import" in code.lower()
        assert "get" in code.lower() or "GET" in code

    def test_post_with_body(self):
        h = HttpRequestHandler()
        node = _make_node(
            "HTTP",
            "n8n-nodes-base.httpRequest",
            {
                "method": "POST",
                "url": "https://api.example.com/submit",
                "sendBody": True,
                "bodyContentType": "json",
            },
        )
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        assert "requests" in ir.pip_packages

    def test_output_is_list(self):
        h = HttpRequestHandler()
        node = _make_node(
            "HTTP",
            "n8n-nodes-base.httpRequest",
            {
                "method": "GET",
                "url": "https://example.com",
            },
        )
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        assert "_output" in code


# ---------------------------------------------------------------------------
# IfNodeHandler
# ---------------------------------------------------------------------------


class TestIfNodeHandler:
    def test_generates_if_branch(self):
        h = IfNodeHandler()
        node = _make_node(
            "IF",
            "n8n-nodes-base.if",
            {
                "conditions": {
                    "conditions": [
                        {
                            "id": "c1",
                            "leftValue": "={{ $json.x }}",
                            "operator": {"type": "number", "operation": "gt"},
                            "rightValue": 5,
                        }
                    ],
                    "combinator": "and",
                }
            },
        )
        node.typeVersion = 2
        ctx = _make_ctx()
        ctx.var_context.register("Prev", "prev")
        ir = h.generate(node, ctx)
        assert ir.kind == IRNodeKind.IF_BRANCH

    def test_true_false_outputs(self):
        h = IfNodeHandler()
        node = _make_node(
            "IF",
            "n8n-nodes-base.if",
            {
                "conditions": {
                    "conditions": [],
                    "combinator": "and",
                }
            },
        )
        node.typeVersion = 2
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        # true/false output variables are in preamble IRNodes inside branches
        true_branch = ir.branches.get("true_branch", [])
        false_branch = ir.branches.get("false_branch", [])
        all_branch_code = ""
        for n in true_branch + false_branch:
            all_branch_code += "\n".join(n.code_lines)
        assert "true_output" in all_branch_code or "false_output" in all_branch_code

    def test_has_condition_line(self):
        h = IfNodeHandler()
        node = _make_node(
            "IF",
            "n8n-nodes-base.if",
            {"conditions": {"conditions": [], "combinator": "and"}},
        )
        node.typeVersion = 2
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        # code_lines contains the "if condition:" line
        code = "\n".join(ir.code_lines)
        assert code.strip().startswith("if ")


# ---------------------------------------------------------------------------
# SetNodeHandler
# ---------------------------------------------------------------------------


class TestSetNodeHandler:
    def test_generates_output(self):
        h = SetNodeHandler()
        node = _make_node(
            "Set",
            "n8n-nodes-base.set",
            {
                "assignments": {
                    "assignments": [{"name": "key", "value": "value", "type": "string"}]
                },
                "options": {},
            },
        )
        node.typeVersion = 3
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        assert "_output" in code

    def test_field_name_in_code(self):
        h = SetNodeHandler()
        node = _make_node(
            "Set",
            "n8n-nodes-base.set",
            {
                "assignments": {
                    "assignments": [
                        {"name": "my_field", "value": "my_value", "type": "string"}
                    ]
                },
                "options": {},
            },
        )
        node.typeVersion = 3
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        assert "my_field" in code


# ---------------------------------------------------------------------------
# FilterNodeHandler
# ---------------------------------------------------------------------------


class TestFilterNodeHandler:
    def test_generates_list_comprehension(self):
        h = FilterNodeHandler()
        node = _make_node(
            "Filter",
            "n8n-nodes-base.filter",
            {
                "conditions": {
                    "conditions": [
                        {
                            "id": "c1",
                            "leftValue": "={{ $json.active }}",
                            "operator": {"type": "boolean", "operation": "true"},
                            "rightValue": "",
                        }
                    ],
                    "combinator": "and",
                }
            },
        )
        ctx = _make_ctx()
        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        assert "for" in code or "filter" in code.lower()


# ---------------------------------------------------------------------------
# NoOpHandler
# ---------------------------------------------------------------------------


class TestNoOpHandler:
    def test_pass_through(self):
        h = NoOpHandler()
        node = _make_node("NoOp", "n8n-nodes-base.noOp")
        ctx = _make_ctx()
        ctx.var_context.register("NoOp", "no_op")
        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        # NoOp should pass output through
        assert "_output" in code


# ---------------------------------------------------------------------------
# FallbackHandler
# ---------------------------------------------------------------------------


class TestFallbackHandler:
    def test_generates_pass_through(self):
        node = _make_node("Mystery", "n8n-nodes-base.unknownXYZ")
        ctx = _make_ctx()
        ir = FALLBACK.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        assert "_output" in code

    def test_has_todo_comment(self):
        node = _make_node("Mystery", "n8n-nodes-base.unknownXYZ")
        ctx = _make_ctx()
        ir = FALLBACK.generate(node, ctx)
        code = "\n".join(ir.code_lines)
        assert "TODO" in code or "pass" in code or "Unsupported" in code


# ---------------------------------------------------------------------------
# AI / LangChain handlers
# ---------------------------------------------------------------------------


class TestAiLangChainHandlers:
    def test_agent_uses_create_agent(self):
        h = AiAgentHandler()
        node = _make_node(
            "AI Agent",
            "@n8n/n8n-nodes-langchain.agent",
            {
                "systemMessage": "Be helpful",
            },
        )
        llm_node = _make_node(
            "OpenAI Chat",
            "@n8n/n8n-nodes-langchain.lmChatOpenAi",
            {
                "model": "gpt-4o-mini",
            },
        )
        ctx = _make_ctx()
        ctx.ai_sub_nodes = {
            "ai_languageModel": [llm_node],
            "ai_tool": [],
            "ai_memory": [],
        }

        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)

        assert "from langchain.agents import create_agent" in code
        assert "create_react_agent" not in code

    def test_basic_chain_uses_core_prompt_template(self):
        h = BasicLlmChainHandler()
        node = _make_node(
            "LLM Chain",
            "@n8n/n8n-nodes-langchain.chainLlm",
            {
                "prompt": "Question: {input}",
            },
        )
        llm_node = _make_node(
            "OpenAI Chat",
            "@n8n/n8n-nodes-langchain.lmChatOpenAi",
            {
                "model": "gpt-4o-mini",
            },
        )
        ctx = _make_ctx()
        ctx.ai_sub_nodes = {"ai_languageModel": [llm_node]}

        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)

        assert "from langchain_core.prompts import PromptTemplate" in code

    def test_sentiment_does_not_use_predict(self):
        h = SentimentAnalysisHandler()
        node = _make_node(
            "Sentiment",
            "@n8n/n8n-nodes-langchain.sentimentAnalysis",
            {
                "inputText": "text",
            },
        )
        llm_node = _make_node(
            "OpenAI Chat",
            "@n8n/n8n-nodes-langchain.lmChatOpenAi",
            {
                "model": "gpt-4o-mini",
            },
        )
        ctx = _make_ctx()
        ctx.ai_sub_nodes = {"ai_languageModel": [llm_node]}

        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)

        assert ".predict(" not in code
        assert ".invoke(" in code

    def test_agent_memory_uses_runnable_with_message_history(self):
        h = AiAgentHandler()
        node = _make_node(
            "AI Agent",
            "@n8n/n8n-nodes-langchain.agent",
            {
                "systemMessage": "Be helpful",
            },
        )
        llm_node = _make_node(
            "OpenAI Chat",
            "@n8n/n8n-nodes-langchain.lmChatOpenAi",
            {
                "model": "gpt-4o-mini",
            },
        )
        mem_node = _make_node(
            "Memory",
            "@n8n/n8n-nodes-langchain.memoryBufferWindow",
            {
                "contextWindowLength": 5,
            },
        )
        ctx = _make_ctx(mode="fastapi")
        ctx.ai_sub_nodes = {
            "ai_languageModel": [llm_node],
            "ai_tool": [],
            "ai_memory": [mem_node],
        }

        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)

        assert "RunnableWithMessageHistory" in code
        assert "config={'configurable': {'session_id': _session_id}}" in code
        assert "from langchain.memory" not in code
        assert "from langchain_classic.memory" not in code

    def test_agent_postgres_tool_closes_connections(self):
        h = AiAgentHandler()
        node = _make_node("AI Agent", "@n8n/n8n-nodes-langchain.agent")
        llm_node = _make_node(
            "OpenAI Chat",
            "@n8n/n8n-nodes-langchain.lmChatOpenAi",
            {
                "model": "gpt-4o-mini",
            },
        )
        tool_node = _make_node(
            "Postgres",
            "n8n-nodes-base.postgresTool",
            {
                "query": "{{ $fromAI('sql_statement') }}",
            },
        )
        ctx = _make_ctx(mode="fastapi")
        ctx.ai_sub_nodes = {
            "ai_languageModel": [llm_node],
            "ai_tool": [tool_node],
            "ai_memory": [],
        }

        ir = h.generate(node, ctx)
        code = "\n".join(ir.code_lines)

        assert "finally:" in code
        assert "_cur.close()" in code
        assert "_c.close()" in code
