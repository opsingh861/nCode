# -*- coding: utf-8 -*-
"""Auto-generated from n8n workflow: 'Untitled Workflow'
Generated at: 2026-03-29T13:24:00Z
"""

import functools
import json
import math
import os
import random
import re
from datetime import date, datetime, timedelta, timezone

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

# --- Sticky note (annotation) ---
# Sticky Note: 'Sticky Note' — "## Try me out Click the 'chat' button at the bottom of the canvas and paste in: ..."
sticky_note_output = []

# --- Sticky note (annotation) ---
# Sticky Note: 'Sticky Note1' — 'This workflow uses a Postgres DB, but you could swap it for a MySQL or SQLite on...'
sticky_note1_output = sticky_note_output


# --- Chat trigger endpoint: POST /chat ---
class ChatRequest(BaseModel):
    message: str | None = None
    text: str | None = None
    input: str | None = None
    sessionId: str | None = None


@app.post("/chat")
async def chat_endpoint(body: ChatRequest) -> JSONResponse:
    load_dotenv()
    payload = body.model_dump(exclude_none=True)
    message = body.message or body.text or body.input or ""
    session_id = body.sessionId or ""
    when_chat_message_received_output = [
        {"json": {"message": message, "sessionId": session_id, "body": payload}}
    ]

    # --- AI Agent (conversational) ---
    import os

    from langchain_openai import ChatOpenAI

    _llm = ChatOpenAI(
        model="gpt-4o-mini", temperature=0.7, api_key=os.environ.get("OPENAI_API_KEY", "")
    )
    from langchain_core.chat_history import InMemoryChatMessageHistory

    _memory_window = 5
    _session_histories = globals().setdefault("_langchain_session_histories", {})

    def _get_session_history(session_id: str):
        _sid = str(session_id or "default")
        if _sid not in _session_histories:
            _session_histories[_sid] = InMemoryChatMessageHistory()
        return _session_histories[_sid]

    def _trim_session_history(session_id: str) -> None:
        _k = int(_memory_window or 0)
        if _k <= 0:
            return
        _hist = _get_session_history(session_id)
        _msgs = list(_hist.messages)
        _max_msgs = _k * 2
        if len(_msgs) <= _max_msgs:
            return
        _hist.clear()
        for _m in _msgs[-_max_msgs:]:
            _hist.add_message(_m)

    _tools = []
    import os

    import psycopg2
    from langchain_core.tools import Tool

    def _pg_tool_postgres(sql: str) -> str:
        _c = None
        _cur = None
        try:
            _c = psycopg2.connect(
                host=os.environ.get("POSTGRES_HOST", "localhost"),
                port=int(os.environ.get("POSTGRES_PORT", "5432")),
                dbname=os.environ.get("POSTGRES_DB", ""),
                user=os.environ.get("POSTGRES_USER", ""),
                password=os.environ.get("POSTGRES_PASSWORD", ""),
            )
            _cur = _c.cursor()
            _cur.execute(sql)
            if _cur.description:
                _rows = _cur.fetchall()
                _cols = [d[0] for d in _cur.description]
                return str([dict(zip(_cols, r)) for r in _rows])
            _c.commit()
            return "Query executed"
        except Exception as _e:
            return f"DB error: {_e}"
        finally:
            if _cur is not None:
                _cur.close()
            if _c is not None:
                _c.close()

    _tools.append(
        Tool(
            name="Postgres",
            func=_pg_tool_postgres,
            description="Execute SQL queries against the database. Input should be a valid SQL statement.",
        )
    )

    from langchain.agents import create_agent

    # AI Agent: 'AI Agent'
    _system_prompt = "You are a helpful AI assistant."

    def _extract_text(_resp):
        if isinstance(_resp, str):
            return _resp
        if isinstance(_resp, dict):
            if isinstance(_resp.get("output"), str):
                return _resp["output"]
            _msgs = _resp.get("messages", [])
            if _msgs:
                _last = _msgs[-1]
                _content = (
                    _last.get("content")
                    if isinstance(_last, dict)
                    else getattr(_last, "content", "")
                )
                if isinstance(_content, list):
                    _parts = []
                    for _p in _content:
                        if isinstance(_p, dict) and _p.get("type") == "text":
                            _parts.append(str(_p.get("text", "")))
                        else:
                            _parts.append(str(_p))
                    _joined = "".join(_parts).strip()
                    return _joined if _joined else str(_resp)
                if _content:
                    return str(_content)
            return str(_resp)
        _content = getattr(_resp, "content", None)
        return str(_content) if _content is not None else str(_resp)

    _agent = None
    _agent_with_history = None
    _agent_setup_error = None
    if _llm is not None:
        try:
            _agent = create_agent(
                model=_llm, tools=_tools if _tools else [], system_prompt=_system_prompt
            )
            if _get_session_history is not None:
                from langchain_core.runnables.history import RunnableWithMessageHistory

                _agent_with_history = RunnableWithMessageHistory(
                    _agent,
                    _get_session_history,
                    input_messages_key="messages",
                    history_messages_key="messages",
                )
        except Exception as _e:
            _agent_setup_error = str(_e)

    ai_agent_output = []
    for _item in when_chat_message_received_output:
        _msg = _item.get("json", {}).get("message", _item.get("json", {}).get("input", ""))
        _session_id = str(_item.get("json", {}).get("sessionId", "") or "default")
        if _agent is not None:
            try:
                if _agent_with_history is not None:
                    _resp = _agent_with_history.invoke(
                        {"messages": [{"role": "user", "content": str(_msg)}]},
                        config={"configurable": {"session_id": _session_id}},
                    )
                    _trim_session_history(_session_id)
                else:
                    _resp = _agent.invoke({"messages": [{"role": "user", "content": str(_msg)}]})
                _result = _extract_text(_resp)
            except Exception as _e:
                _result = f"Agent error: {_e}"
        elif _llm is not None:
            try:
                _resp = _llm.invoke(_msg)
                _result = _resp.content if hasattr(_resp, "content") else str(_resp)
                if _agent_setup_error:
                    _result = f"Agent setup warning: {_agent_setup_error}\n\n{_result}"
            except Exception as _e:
                _result = f"LLM error: {_e}"
        else:
            _result = "LLM not configured"
        ai_agent_output.append({"json": {"output": _result, "input": _msg}})

    return JSONResponse(ai_agent_output[0]["json"] if ai_agent_output else {})


if __name__ == "__main__":
    uvicorn.run("__main__:app", host="0.0.0.0", port=8000, reload=False)
