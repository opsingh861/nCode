"""AI/LangChain node handlers.

Handles the cluster pattern: an AI root node (Agent, LLM Chain, etc.)
is composed with its sub-nodes (LLM model, memory, tools, etc.) via
non-main connection types. The handler collects all sub-nodes from
GenerationContext.ai_sub_nodes and emits a single composed Python block.
"""

from __future__ import annotations

import re
from typing import Any

from backend.core.ir import IRNode, IRNodeKind
from backend.handlers.base import GenerationContext
from backend.handlers.registry import register
from backend.models.workflow import N8nNode


def _safe_var(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_") or "node"
    return f"n_{s}" if s[0].isdigit() else s


def _get_sub_nodes(ctx: GenerationContext, conn_type: str) -> list[N8nNode]:
    return ctx.ai_sub_nodes.get(conn_type, [])


def _emit_llm_init(
    llm_nodes: list[N8nNode], ctx: GenerationContext
) -> tuple[str, list[str], list[str]]:
    """Return (llm_var_name, code_lines, packages) for the LLM model sub-node."""
    if not llm_nodes:
        return ("None", ["_llm = None  # No LLM model connected"], [])

    llm_node = llm_nodes[0]
    llm_type = llm_node.type.lower()
    params = llm_node.parameters
    temperature = params.get("options", {}).get(
        "temperature", params.get("temperature", 0.7)
    )

    def _extract_model(raw: Any, default: str) -> str:
        """Extract model name from n8n's resource-locator dict or plain string."""
        if isinstance(raw, dict):
            return str(raw.get("value", raw.get("id", default)))
        return str(raw) if raw else default

    if "openai" in llm_type or "chatgpt" in llm_type:
        model_name = _extract_model(
            params.get("model", params.get("modelId")), "gpt-4o"
        )
        lines = [
            "import os",
            "from langchain_openai import ChatOpenAI",
            f'_llm = ChatOpenAI(model="{model_name}", temperature={temperature}, api_key=os.environ.get("OPENAI_API_KEY", ""))',
        ]
        return ("_llm", lines, ["langchain-openai"])

    elif "anthropic" in llm_type or "claude" in llm_type:
        model_name = _extract_model(
            params.get("model", params.get("modelId")), "claude-3-5-sonnet-20241022"
        )
        lines = [
            "import os",
            "from langchain_anthropic import ChatAnthropic",
            f'_llm = ChatAnthropic(model="{model_name}", temperature={temperature}, api_key=os.environ.get("ANTHROPIC_API_KEY", ""))',
        ]
        return ("_llm", lines, ["langchain-anthropic"])

    elif "gemini" in llm_type or "google" in llm_type:
        model_name = _extract_model(
            params.get("model", params.get("modelName", params.get("modelId"))),
            "gemini-1.5-pro",
        )
        lines = [
            "import os",
            "from langchain_google_genai import ChatGoogleGenerativeAI",
            f'_llm = ChatGoogleGenerativeAI(model="{model_name}", temperature={temperature}, google_api_key=os.environ.get("GOOGLE_API_KEY", ""))',
        ]
        return ("_llm", lines, ["langchain-google-genai"])

    else:
        lines = [f"_llm = None  # TODO: unsupported LLM type: {llm_node.type!r}"]
        return ("None", lines, [])


def _emit_memory_init(
    mem_nodes: list[N8nNode], ctx: GenerationContext
) -> tuple[str, list[str], list[str]]:
    """Return (memory_var, code_lines, packages) for memory sub-node."""
    if not mem_nodes:
        return ("None", [], [])

    mem_node = mem_nodes[0]
    mem_type = mem_node.type.lower()
    params = mem_node.parameters

    if "postgres" in mem_type or "postgreschat" in mem_type:
        k = int(params.get("maxHistorySize", params.get("contextWindowLength", 5)) or 5)
        lines = [
            "import os",
            "from langchain_core.chat_history import InMemoryChatMessageHistory",
            f"_memory_window = {k}",
            "_fallback_histories = globals().setdefault('_langchain_session_histories', {})",
            "_postgres_history_table = os.environ.get('LANGCHAIN_CHAT_TABLE', 'chat_history')",
            "_postgres_uri = os.environ.get('POSTGRES_URI', '')",
            "_postgres_history_conn = globals().get('_langchain_postgres_history_conn')",
            "try:",
            "    import psycopg",
            "    from langchain_postgres import PostgresChatMessageHistory",
            "    if _postgres_uri and _postgres_history_conn is None:",
            "        _postgres_history_conn = psycopg.connect(_postgres_uri)",
            "        globals()['_langchain_postgres_history_conn'] = _postgres_history_conn",
            "        PostgresChatMessageHistory.create_tables(_postgres_history_conn, _postgres_history_table)",
            "except Exception:",
            "    _postgres_history_conn = None",
            "",
            "def _get_session_history(session_id: str):",
            "    _sid = str(session_id or 'default')",
            "    if _postgres_history_conn is not None:",
            "        return PostgresChatMessageHistory(_postgres_history_table, _sid, sync_connection=_postgres_history_conn)",
            "    if _sid not in _fallback_histories:",
            "        _fallback_histories[_sid] = InMemoryChatMessageHistory()",
            "    return _fallback_histories[_sid]",
            "",
            "def _trim_session_history(session_id: str) -> None:",
            "    _k = int(_memory_window or 0)",
            "    if _k <= 0:",
            "        return",
            "    _hist = _get_session_history(session_id)",
            "    _msgs = list(getattr(_hist, 'messages', []))",
            "    _max_msgs = _k * 2",
            "    if len(_msgs) <= _max_msgs:",
            "        return",
            "    _hist.clear()",
            "    for _m in _msgs[-_max_msgs:]:",
            "        _hist.add_message(_m)",
        ]
        return (
            "_get_session_history",
            lines,
            ["langchain", "langchain-core", "langchain-postgres", "psycopg[binary]"],
        )

    if "buffer" in mem_type and "window" not in mem_type:
        k = int(
            params.get("maxHistorySize", params.get("contextWindowLength", 10)) or 10
        )
    elif "window" in mem_type or "bufferwindow" in mem_type:
        k = int(params.get("maxHistorySize", params.get("contextWindowLength", 5)) or 5)
    else:
        k = 10

    lines = [
        "from langchain_core.chat_history import InMemoryChatMessageHistory",
        f"_memory_window = {k}",
        "_session_histories = globals().setdefault('_langchain_session_histories', {})",
        "",
        "def _get_session_history(session_id: str):",
        "    _sid = str(session_id or 'default')",
        "    if _sid not in _session_histories:",
        "        _session_histories[_sid] = InMemoryChatMessageHistory()",
        "    return _session_histories[_sid]",
        "",
        "def _trim_session_history(session_id: str) -> None:",
        "    _k = int(_memory_window or 0)",
        "    if _k <= 0:",
        "        return",
        "    _hist = _get_session_history(session_id)",
        "    _msgs = list(_hist.messages)",
        "    _max_msgs = _k * 2",
        "    if len(_msgs) <= _max_msgs:",
        "        return",
        "    _hist.clear()",
        "    for _m in _msgs[-_max_msgs:]:",
        "        _hist.add_message(_m)",
    ]
    return ("_get_session_history", lines, ["langchain", "langchain-core"])


def _emit_tools_init(
    tool_nodes: list[N8nNode], ctx: GenerationContext
) -> tuple[str, list[str], list[str]]:
    """Return (tools_var, code_lines, packages) for tool sub-nodes."""
    if not tool_nodes:
        return ("[]", [], [])

    lines = ["_tools = []"]
    packages = ["langchain"]

    for tool_node in tool_nodes:
        tool_type = tool_node.type.lower()
        params = tool_node.parameters

        if "calculator" in tool_type:
            lines += [
                "from langchain_core.tools import Tool",
                "_tools.append(Tool(name='Calculator', func=lambda x: str(eval(x)), description='Useful for math calculations'))",
            ]
        elif "serpapi" in tool_type or "google" in tool_type and "search" in tool_type:
            lines += [
                "import os",
                "from langchain_community.utilities import SerpAPIWrapper",
                "from langchain_core.tools import Tool",
                '_serp = SerpAPIWrapper(serpapi_api_key=os.environ.get("SERPAPI_API_KEY", ""))',
                "_tools.append(Tool(name='Search', func=_serp.run, description='Useful for web searches'))",
            ]
            packages += ["google-search-results", "langchain-community"]
        elif "code" in tool_type or "python" in tool_type:
            lines += [
                "from langchain_core.tools import Tool",
                "def _python_exec_tool(code: str) -> str:",
                "    _locals = {}",
                "    try:",
                "        exec(code, {}, _locals)",
                "        if 'result' in _locals:",
                "            return str(_locals['result'])",
                "        return 'Code executed'",
                "    except Exception as _e:",
                "        return f'Python tool error: {_e}'",
                "_tools.append(Tool(name='Python', func=_python_exec_tool, description='Execute short Python snippets. Store final value in variable result.'))",
            ]
        elif "postgres" in tool_type or "mysql" in tool_type or "sql" in tool_type:
            safe_tool = re.sub(r"[^a-z0-9]", "_", tool_node.name.lower().strip())
            lines += [
                "import os, psycopg2",
                "from langchain_core.tools import Tool",
                f"def _pg_tool_{safe_tool}(sql: str) -> str:",
                f"    _c = None",
                f"    _cur = None",
                f"    try:",
                f'        _c = psycopg2.connect(host=os.environ.get("POSTGRES_HOST","localhost"), port=int(os.environ.get("POSTGRES_PORT","5432")), dbname=os.environ.get("POSTGRES_DB",""), user=os.environ.get("POSTGRES_USER",""), password=os.environ.get("POSTGRES_PASSWORD",""))',
                f"        _cur = _c.cursor()",
                f"        _cur.execute(sql)",
                f"        if _cur.description:",
                f"            _rows = _cur.fetchall()",
                f"            _cols = [d[0] for d in _cur.description]",
                f"            return str([dict(zip(_cols, r)) for r in _rows])",
                f"        _c.commit()",
                f'        return "Query executed"',
                f"    except Exception as _e:",
                f'        return f"DB error: {{_e}}"',
                f"    finally:",
                f"        if _cur is not None:",
                f"            _cur.close()",
                f"        if _c is not None:",
                f"            _c.close()",
                f"_tools.append(Tool(name={tool_node.name!r}, func=_pg_tool_{safe_tool}, description='Execute SQL queries against the database. Input should be a valid SQL statement.'))",
            ]
            packages += ["psycopg2-binary"]
        elif "http" in tool_type:
            tool_url = str(tool_node.parameters.get("url", ""))
            lines += [
                "import requests",
                "from langchain_core.tools import Tool",
                f"_tools.append(Tool(name={tool_node.name!r}, func=lambda q: requests.get({tool_url!r}, params={{'q': q}}).text[:2000], description='Make HTTP requests. Input is the query string.'))",
            ]
        else:
            tool_name = str(params.get("name", tool_node.name))
            lines += [
                f"# Tool: {tool_node.type!r} — TODO implement",
                f"# _tools.append(...)  # {tool_name!r}",
            ]

    return ("_tools", lines, packages)


# ---------------------------------------------------------------------------
# AI Agent
# ---------------------------------------------------------------------------


@register(
    "@n8n/n8n-nodes-langchain.agent",
    "@n8n/n8n-nodes-langchain.openAiAssistant",
)
class AiAgentHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        llm_nodes = _get_sub_nodes(ctx, "ai_languageModel")
        mem_nodes = _get_sub_nodes(ctx, "ai_memory")
        tool_nodes = _get_sub_nodes(ctx, "ai_tool")

        llm_var, llm_lines, llm_pkgs = _emit_llm_init(llm_nodes, ctx)
        mem_var, mem_lines, mem_pkgs = _emit_memory_init(mem_nodes, ctx)
        tools_var, tools_lines, tools_pkgs = _emit_tools_init(tool_nodes, ctx)

        agent_type = str(params.get("agentType", "conversational")).lower()
        system_message = str(params.get("systemMessage", params.get("text", "")))

        code_lines = (
            llm_lines
            + mem_lines
            + tools_lines
            + [
                "",
                "from langchain.agents import create_agent",
                "",
                f"# AI Agent: {node.name!r}",
            ]
        )

        system_prefix = (
            "You are a helpful AI assistant.\n\n" + system_message
            if system_message
            else "You are a helpful AI assistant."
        )

        code_lines += [
            f"_system_prompt = {system_prefix!r}",
            "",
            "def _extract_text(_resp):",
            "    if isinstance(_resp, str):",
            "        return _resp",
            "    if isinstance(_resp, dict):",
            "        if isinstance(_resp.get('output'), str):",
            "            return _resp['output']",
            "        _msgs = _resp.get('messages', [])",
            "        if _msgs:",
            "            _last = _msgs[-1]",
            "            _content = _last.get('content') if isinstance(_last, dict) else getattr(_last, 'content', '')",
            "            if isinstance(_content, list):",
            "                _parts = []",
            "                for _p in _content:",
            "                    if isinstance(_p, dict) and _p.get('type') == 'text':",
            "                        _parts.append(str(_p.get('text', '')))",
            "                    else:",
            "                        _parts.append(str(_p))",
            "                _joined = ''.join(_parts).strip()",
            "                return _joined if _joined else str(_resp)",
            "            if _content:",
            "                return str(_content)",
            "        return str(_resp)",
            "    _content = getattr(_resp, 'content', None)",
            "    return str(_content) if _content is not None else str(_resp)",
        ]

        code_lines += [
            "",
            "_agent = None",
            "_agent_with_history = None",
            "_agent_setup_error = None",
            f"if _llm is not None:",
            f"    try:",
            f"        _agent = create_agent(model=_llm, tools={tools_var} if {tools_var} else [], system_prompt=_system_prompt)",
            f"        if {mem_var} is not None:",
            "            from langchain_core.runnables.history import RunnableWithMessageHistory",
            f"            _agent_with_history = RunnableWithMessageHistory(_agent, {mem_var}, input_messages_key='messages', history_messages_key='messages')",
            f"    except Exception as _e:",
            f"        _agent_setup_error = str(_e)",
            "",
            f"{var}_output = []",
            f"for _item in {prev_var}:",
            f"    _msg = _item.get('json', {{}}).get('message', _item.get('json', {{}}).get('input', ''))",
            f"    _session_id = str(_item.get('json', {{}}).get('sessionId', '') or 'default')",
            f"    if _agent is not None:",
            f"        try:",
            f"            if _agent_with_history is not None:",
            f"                _resp = _agent_with_history.invoke({{'messages': [{{'role': 'user', 'content': str(_msg)}}]}}, config={{'configurable': {{'session_id': _session_id}}}})",
            f"                _trim_session_history(_session_id)",
            f"            else:",
            f"                _resp = _agent.invoke({{'messages': [{{'role': 'user', 'content': str(_msg)}}]}})",
            f"            _result = _extract_text(_resp)",
            f"        except Exception as _e:",
            f"            _result = f'Agent error: {{_e}}'",
            f"    elif _llm is not None:",
            f"        try:",
            f"            _resp = _llm.invoke(_msg)",
            f"            _result = _resp.content if hasattr(_resp, 'content') else str(_resp)",
            f"            if _agent_setup_error:",
            f"                _result = f'Agent setup warning: {{_agent_setup_error}}\\n\\n{{_result}}'",
            f"        except Exception as _e:",
            f"            _result = f'LLM error: {{_e}}'",
            f"    else:",
            f"        _result = 'LLM not configured'",
            f"    {var}_output.append({{'json': {{'output': _result, 'input': _msg}}}})",
        ]

        all_pkgs = list(set(llm_pkgs + mem_pkgs + tools_pkgs + ["langchain"]))

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            pip_packages=all_pkgs,
            code_lines=code_lines,
            comment=f"AI Agent ({agent_type})",
        )

    def supported_operations(self) -> list[str]:
        return ["@n8n/n8n-nodes-langchain.agent"]

    def required_packages(self) -> list[str]:
        return ["langchain"]


# ---------------------------------------------------------------------------
# Basic LLM Chain
# ---------------------------------------------------------------------------


@register("@n8n/n8n-nodes-langchain.chainLlm")
class BasicLlmChainHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        llm_nodes = _get_sub_nodes(ctx, "ai_languageModel")
        output_parser_nodes = _get_sub_nodes(ctx, "ai_outputParser")
        llm_var, llm_lines, llm_pkgs = _emit_llm_init(llm_nodes, ctx)

        prompt_text = ctx.resolve_expr(
            str(params.get("prompt", params.get("text", "{input}")))
        )

        code_lines = llm_lines + [
            "",
            "from langchain_core.prompts import PromptTemplate",
            "from langchain_core.output_parsers import StrOutputParser",
            "",
            f"_chain_prompt = PromptTemplate.from_template({prompt_text})",
            f"_chain = _chain_prompt | _llm | StrOutputParser() if _llm is not None else None",
            "",
            f"{var}_output = []",
            f"for _item in {prev_var}:",
            f"    _input = _item.get('json', {{}})",
            f"    if _chain is not None:",
            f"        try:",
            f"            _result = _chain.invoke(_input)",
            f"        except Exception as _e:",
            f"            _result = f'LLM error: {{_e}}'",
            f"    else:",
            f"        _result = 'LLM not configured'",
            f"    {var}_output.append({{'json': {{'output': _result}}}})",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            pip_packages=list(set(llm_pkgs + ["langchain"])),
            code_lines=code_lines,
            comment="Basic LLM Chain",
        )

    def supported_operations(self) -> list[str]:
        return ["@n8n/n8n-nodes-langchain.chainLlm"]

    def required_packages(self) -> list[str]:
        return ["langchain"]


# ---------------------------------------------------------------------------
# Summarization Chain
# ---------------------------------------------------------------------------


@register("@n8n/n8n-nodes-langchain.chainSummarization")
class SummarizationChainHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        llm_nodes = _get_sub_nodes(ctx, "ai_languageModel")
        llm_var, llm_lines, llm_pkgs = _emit_llm_init(llm_nodes, ctx)

        chain_type = str(params.get("type", "map_reduce")).lower()
        field_name = str(params.get("dataPropertyName", "text"))

        code_lines = llm_lines + [
            "",
            "from langchain_core.output_parsers import StrOutputParser",
            "from langchain_core.prompts import PromptTemplate",
            "",
            f"_summary_prompt = PromptTemplate.from_template('Summarize the following text ({chain_type}):\\n\\n{{text}}')",
            "_summary_chain = _summary_prompt | _llm | StrOutputParser() if _llm is not None else None",
            "",
            f"{var}_output = []",
            f"for _item in {prev_var}:",
            f"    _text = _item.get('json', {{}}).get('{field_name}', '')",
            f"    if _summary_chain is not None:",
            f"        _result = _summary_chain.invoke({{'text': str(_text)}})",
            f"    else:",
            f"        _result = 'LLM not configured'",
            f"    {var}_output.append({{'json': {{'summary': _result}}}})",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            pip_packages=list(set(llm_pkgs + ["langchain"])),
            code_lines=code_lines,
            comment=f"Summarization Chain ({chain_type})",
        )

    def supported_operations(self) -> list[str]:
        return ["@n8n/n8n-nodes-langchain.chainSummarization"]

    def required_packages(self) -> list[str]:
        return ["langchain"]


# ---------------------------------------------------------------------------
# Q&A Chain / Retrieval QA
# ---------------------------------------------------------------------------


@register("@n8n/n8n-nodes-langchain.chainRetrievalQa")
class QaChainHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        llm_nodes = _get_sub_nodes(ctx, "ai_languageModel")
        retriever_nodes = _get_sub_nodes(ctx, "ai_retriever")
        llm_var, llm_lines, llm_pkgs = _emit_llm_init(llm_nodes, ctx)

        code_lines = llm_lines + [
            "",
            "# TODO: configure retriever from connected vector store",
            "_retriever = None",
            "",
            f"{var}_output = []",
            f"for _item in {prev_var}:",
            f"    _question = _item.get('json', {{}}).get('question', _item.get('json', {{}}).get('input', ''))",
            f"    if _llm is not None and _retriever is not None:",
            f"        _result = _llm.invoke(f'Use this context if helpful: {{_retriever}}\\n\\nQuestion: {{_question}}').content",
            f"    elif _llm is not None:",
            f"        _resp = _llm.invoke(_question)",
            f"        _result = _resp.content if hasattr(_resp, 'content') else str(_resp)",
            f"    else:",
            f"        _result = 'LLM not configured'",
            f"    {var}_output.append({{'json': {{'answer': _result}}}})",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            pip_packages=list(set(llm_pkgs + ["langchain"])),
            code_lines=code_lines,
            comment="Q&A (Retrieval) Chain",
        )

    def supported_operations(self) -> list[str]:
        return ["@n8n/n8n-nodes-langchain.chainRetrievalQa"]

    def required_packages(self) -> list[str]:
        return ["langchain"]


# ---------------------------------------------------------------------------
# Text Classifier
# ---------------------------------------------------------------------------


@register("@n8n/n8n-nodes-langchain.textClassifier")
class TextClassifierHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        llm_nodes = _get_sub_nodes(ctx, "ai_languageModel")
        llm_var, llm_lines, llm_pkgs = _emit_llm_init(llm_nodes, ctx)

        categories = params.get("categories", {}).get("categories", [])
        cat_names = [
            str(c.get("category", f"category_{i}"))
            for i, c in enumerate(categories)
            if isinstance(c, dict)
        ]
        field = str(params.get("inputText", "text"))

        code_lines = llm_lines + [
            "",
            "from langchain_core.output_parsers import StrOutputParser",
            "from langchain_core.prompts import PromptTemplate",
            "",
            f"_categories = {cat_names!r}",
            f"_prompt_tmpl = 'Classify the following text into one of these categories: {{categories}}\\n\\nText: {{text}}\\n\\nCategory:'",
            f"_classifier_prompt = PromptTemplate.from_template(_prompt_tmpl)",
            "_classifier_chain = _classifier_prompt | _llm | StrOutputParser() if _llm is not None else None",
            "",
            f"{var}_output = []",
            f"for _item in {prev_var}:",
            f"    _text = _item.get('json', {{}}).get('{field}', '')",
            f"    if _classifier_chain is not None:",
            f"        _result = str(_classifier_chain.invoke({{'categories': ', '.join(_categories), 'text': _text}})).strip()",
            f"    else:",
            f"        _result = _categories[0] if _categories else 'unknown'",
            f"    {var}_output.append({{'json': {{**_item.get('json', {{}}), 'classification': _result}}}})",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            pip_packages=list(set(llm_pkgs + ["langchain"])),
            code_lines=code_lines,
            comment="Text Classifier",
        )

    def supported_operations(self) -> list[str]:
        return ["@n8n/n8n-nodes-langchain.textClassifier"]

    def required_packages(self) -> list[str]:
        return ["langchain"]


# ---------------------------------------------------------------------------
# Information Extractor
# ---------------------------------------------------------------------------


@register("@n8n/n8n-nodes-langchain.informationExtractor")
class InformationExtractorHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        llm_nodes = _get_sub_nodes(ctx, "ai_languageModel")
        llm_var, llm_lines, llm_pkgs = _emit_llm_init(llm_nodes, ctx)

        attributes_spec = params.get("attributes", {})
        attributes = (
            attributes_spec.get("attributes", [])
            if isinstance(attributes_spec, dict)
            else []
        )
        field = str(params.get("text", "text"))

        attr_list = [
            str(a.get("name", ""))
            for a in attributes
            if isinstance(a, dict) and a.get("name")
        ]

        code_lines = llm_lines + [
            "",
            "import json as _json_mod",
            "",
            f"_attributes = {attr_list!r}",
            f"_extract_prompt = f'Extract the following attributes from the text: {{_attributes}}.\\nReturn as JSON.\\n\\nText: {{{{text}}}}\\n\\nJSON:'",
            "",
            f"{var}_output = []",
            f"for _item in {prev_var}:",
            f"    _text = _item.get('json', {{}}).get('{field}', '')",
            f"    if _llm is not None:",
            f"        try:",
            f"            _resp = _llm.invoke(_extract_prompt.format(text=_text))",
            f"            _raw = _resp.content if hasattr(_resp, 'content') else str(_resp)",
            f"            _raw = _raw.strip()",
            f"            if _raw.startswith('```') and _raw.endswith('```'):",
            f"                _raw = _raw.strip('`')",
            f"                _raw = _raw.replace('json\\n', '', 1).strip()",
            f"            _extracted = _json_mod.loads(_raw)",
            f"        except Exception:",
            f"            _extracted = {{}}",
            f"    else:",
            f"        _extracted = {{}}",
            f"    {var}_output.append({{'json': {{**_item.get('json', {{}}), **_extracted}}}})",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            pip_packages=list(set(llm_pkgs + ["langchain"])),
            code_lines=code_lines,
            comment="Information Extractor",
        )

    def supported_operations(self) -> list[str]:
        return ["@n8n/n8n-nodes-langchain.informationExtractor"]

    def required_packages(self) -> list[str]:
        return ["langchain"]


# ---------------------------------------------------------------------------
# Sentiment Analysis
# ---------------------------------------------------------------------------


@register("@n8n/n8n-nodes-langchain.sentimentAnalysis")
class SentimentAnalysisHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        llm_nodes = _get_sub_nodes(ctx, "ai_languageModel")
        llm_var, llm_lines, llm_pkgs = _emit_llm_init(llm_nodes, ctx)

        field = str(params.get("inputText", "text"))

        code_lines = llm_lines + [
            "",
            f"{var}_output = []",
            f"for _item in {prev_var}:",
            f"    _text = _item.get('json', {{}}).get('{field}', '')",
            f"    if _llm is not None:",
            f"        _prompt = f'Classify the sentiment of the following text as positive, negative, or neutral.\\n\\nText: {{_text}}\\n\\nSentiment:'",
            f"        _resp = _llm.invoke(_prompt)",
            f"        _sentiment = str(_resp.content if hasattr(_resp, 'content') else _resp).strip().lower()",
            f"    else:",
            f"        _sentiment = 'neutral'",
            f"    {var}_output.append({{'json': {{**_item.get('json', {{}}), 'sentiment': _sentiment}}}})",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            pip_packages=list(set(llm_pkgs + ["langchain"])),
            code_lines=code_lines,
            comment="Sentiment Analysis",
        )

    def supported_operations(self) -> list[str]:
        return ["@n8n/n8n-nodes-langchain.sentimentAnalysis"]

    def required_packages(self) -> list[str]:
        return ["langchain"]


# ---------------------------------------------------------------------------
# LLM Sub-nodes (model nodes) — these are consumed by root nodes above,
# but we register them so they don't fall through to FallbackHandler.
# They produce pass-through output when encountered standalone.
# ---------------------------------------------------------------------------

_LLM_SUB_NODE_TYPES = [
    "@n8n/n8n-nodes-langchain.lmChatOpenAi",
    "@n8n/n8n-nodes-langchain.lmChatAnthropic",
    "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
    "@n8n/n8n-nodes-langchain.lmChatGroq",
    "@n8n/n8n-nodes-langchain.lmChatMistralCloud",
    "@n8n/n8n-nodes-langchain.lmChatOllama",
    "@n8n/n8n-nodes-langchain.lmChatAwsBedrock",
    "@n8n/n8n-nodes-langchain.lmChatAzureOpenAi",
    "@n8n/n8n-nodes-langchain.memoryBufferWindow",
    "@n8n/n8n-nodes-langchain.memoryBufferWindowV2",
    "@n8n/n8n-nodes-langchain.memoryPostgresChat",
    "@n8n/n8n-nodes-langchain.memoryRedisChat",
    "@n8n/n8n-nodes-langchain.memoryMotorhead",
    "@n8n/n8n-nodes-langchain.memoryXata",
    "@n8n/n8n-nodes-langchain.toolCalculator",
    "@n8n/n8n-nodes-langchain.toolSerpApi",
    "@n8n/n8n-nodes-langchain.toolCode",
    "@n8n/n8n-nodes-langchain.toolHttpRequest",
    "@n8n/n8n-nodes-langchain.toolWorkflow",
    "@n8n/n8n-nodes-langchain.toolVectorStore",
    # Note: n8n-nodes-base.postgresTool has its own handler in databases.py
    # and is handled inline by _emit_tools_init — not listed here.
    "@n8n/n8n-nodes-langchain.outputParserStructured",
    "@n8n/n8n-nodes-langchain.outputParserAutofixing",
    "@n8n/n8n-nodes-langchain.retrieverVectorStore",
    "@n8n/n8n-nodes-langchain.vectorStoreInMemory",
    "@n8n/n8n-nodes-langchain.vectorStorePinecone",
    "@n8n/n8n-nodes-langchain.vectorStoreSupabase",
    "@n8n/n8n-nodes-langchain.embeddingsOpenAi",
    "@n8n/n8n-nodes-langchain.embeddingsAzureOpenAi",
    "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter",
    "@n8n/n8n-nodes-langchain.textSplitterTokenSplitter",
    "@n8n/n8n-nodes-langchain.documentDefaultDataLoader",
    "@n8n/n8n-nodes-langchain.documentBinaryInputLoader",
    "@n8n/n8n-nodes-langchain.documentJsonInputLoader",
]


@register(*_LLM_SUB_NODE_TYPES)
class AiSubNodeHandler:
    """Stub handler for AI sub-nodes (they are consumed by root AI nodes)."""

    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=[
                f"# AI sub-node: {node.type!r} — handled by parent AI root node",
                f"{var}_output = {prev_var}",
            ],
            comment=f"AI sub-node: {node.type!r}",
        )

    def supported_operations(self) -> list[str]:
        return _LLM_SUB_NODE_TYPES

    def required_packages(self) -> list[str]:
        return []
