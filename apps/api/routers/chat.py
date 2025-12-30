from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from openai import OpenAI

from apps.api.mcp_client import MCPMockClient
from apps.api.models import ChatRequest, ChatResponse

from amex_core.observability import log_tool_call_start, log_tool_call_end, new_request_id
from apps.api.prompts.loader import load_prompt # load system prompt

system_prompt = load_prompt("system-prompt.md")


router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory conversation (mock). Replace with Redis/DB in real prod.
_CONVERSATION: list[dict[str, Any]] = []

# OpenAI
client = OpenAI()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# MCP server path (http)
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8765/mcp")
mcp = MCPMockClient(MCP_SERVER_URL)


def _mcp_tools_to_openai_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert MCP tool schemas to OpenAI Chat Completions tools format.
    """
    out: list[dict[str, Any]] = []
    for t in mcp_tools:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", "") or "",
                    "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
                },
            }
        )
    return out


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    request_id = new_request_id()

    msg = (req.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")

    # 1) List tools from MCP
    tools_meta = await mcp.list_tools()
    tools_for_openai = _mcp_tools_to_openai_tools(
        [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools_meta]
    )

    # 2) Prepare messages
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": msg},
    ]

    tools_used: list[str] = []

    # 3) Tool-calling loop
    for _ in range(8):  # loop guard
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools_for_openai,
            tool_choice="auto",
        )

        msg_obj = resp.choices[0].message
        tool_calls = getattr(msg_obj, "tool_calls", None)

        # If tool calls are requested, execute and continue
        if tool_calls:
            # Add assistant tool-call message
            messages.append(
                {
                    "role": "assistant",
                    "content": msg_obj.content or "",
                    "tool_calls": [tc.model_dump() for tc in tool_calls],
                }
            )

            for tc in tool_calls:
                tool_name = tc.function.name
                tools_used.append(tool_name)

                # Parse tool args
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    if not isinstance(args, dict):
                        args = {}
                except json.JSONDecodeError:
                    args = {}

                # ✅ Structured tool logging start
                start = log_tool_call_start(request_id, tool_name, args)

                # Call MCP tool with logging end
                try:
                    tool_result = await mcp.call_tool(tool_name, args)
                    log_tool_call_end(request_id, tool_name, start, ok=True)
                except Exception as e:
                    log_tool_call_end(request_id, tool_name, start, ok=False, error=str(e))
                    raise

                # Send tool output back to model
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

            continue

        # Final response (no tool calls)
        final_text = msg_obj.content or "I couldn't generate a response."
        _CONVERSATION.append({"role": "user", "content": msg})
        _CONVERSATION.append({"role": "assistant", "content": final_text})

        # NOTE: ChatResponse model currently doesn't include request_id.
        # If you want request_id returned, add it to ChatResponse model.
        return ChatResponse(reply=final_text, tools_used=tools_used, suggestions=[])

    # loop guard hit
    return ChatResponse(
        reply="I’m having trouble completing that request right now. Try rephrasing or asking more specifically.",
        tools_used=tools_used,
        suggestions=[],
    )


@router.get("/history")
def history() -> list[dict]:
    return _CONVERSATION


@router.post("/clear")
def clear() -> dict:
    _CONVERSATION.clear()
    return {"ok": True}
