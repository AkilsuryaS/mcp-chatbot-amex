from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import json
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from openai import OpenAI

from apps.api.mcp_client import MCPMockClient
from apps.api.models import ChatRequest, ChatResponse

from amex_core.observability import log_tool_call_start, log_tool_call_end, new_request_id

router = APIRouter(prefix="/chat", tags=["chat"])

client = OpenAI()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8765/mcp")
mcp = MCPMockClient(MCP_SERVER_URL)

# -------------------------
# Per-session store
# -------------------------
_SESSION_MEMORY: Dict[str, Dict[str, Any]] = {}
_SESSION_HISTORY: Dict[str, List[Dict[str, Any]]] = {}

MAX_HISTORY_TURNS = 10  # last 10 messages (user/assistant)


def _get_session_state(session_id: str) -> Dict[str, Any]:
    if session_id not in _SESSION_MEMORY:
        _SESSION_MEMORY[session_id] = {
            "last_card_id": None,
            "last_customer_id": None,
            "last_compared_card_ids": None,
            "last_monthly_spend_inr": None,
        }
    if session_id not in _SESSION_HISTORY:
        _SESSION_HISTORY[session_id] = []
    return _SESSION_MEMORY[session_id]


def _render_memory(state: Dict[str, Any]) -> str:
    parts = []
    for k in ["last_card_id", "last_customer_id", "last_compared_card_ids", "last_monthly_spend_inr"]:
        v = state.get(k)
        if v is not None and v != []:
            parts.append(f"{k}={v}")
    return "Conversation memory: " + (", ".join(parts) if parts else "(empty)")


def _mcp_tools_to_openai_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _normalize_card_id(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()

    # strict mappings
    mapping = {
        "gold": "gold",
        "platinum": "platinum",
        "green": "green",
        "business_platinum": "business_platinum",
        "blue_cash_preferred": "blue_cash_preferred",
    }
    for k, v in mapping.items():
        if k in t:
            # special case: "business platinum"
            if v == "platinum" and "business" in t:
                return "business_platinum"
            return v

    if "business platinum" in t:
        return "business_platinum"
    if "blue cash preferred" in t:
        return "blue_cash_preferred"

    return None


def _is_annual_fee_question(user_text: str) -> bool:
    t = user_text.lower()
    return "annual fee" in t or "fee" in t and "annual" in t


def _is_eligibility_question(user_text: str) -> bool:
    t = user_text.lower()
    return "eligible" in t or "eligibility" in t or "am i eligible" in t


def _update_memory_from_tool_call(state: Dict[str, Any], tool_name: str, args: Dict[str, Any]) -> None:
    if tool_name == "search_cards":
        cid = _normalize_card_id(str(args.get("query", "")))
        if cid:
            state["last_card_id"] = cid

    elif tool_name == "compare_cards":
        ids = args.get("card_ids")
        if isinstance(ids, list) and ids:
            state["last_compared_card_ids"] = ids
            if isinstance(ids[0], str):
                state["last_card_id"] = ids[0]

    elif tool_name == "check_eligibility":
        cid = _normalize_card_id(str(args.get("card_id", "")))
        if cid:
            state["last_card_id"] = cid
        cust = args.get("customer_id")
        if isinstance(cust, str) and cust.strip():
            state["last_customer_id"] = cust.strip()

    elif tool_name == "rewards_estimate":
        cid = _normalize_card_id(str(args.get("card_id", "")))
        if cid:
            state["last_card_id"] = cid
        spend = args.get("monthly_spend_inr")
        try:
            if spend is not None:
                state["last_monthly_spend_inr"] = int(spend)
        except Exception:
            pass


def _infer_last_card_from_assistant_text(text: str) -> Optional[str]:
    """
    Backup heuristic: if assistant recommended a card by name, store it.
    """
    t = (text or "").lower()
    if "gold card" in t:
        return "gold"
    if "green card" in t:
        return "green"
    if "business platinum" in t:
        return "business_platinum"
    if "platinum card" in t:
        return "platinum"
    if "blue cash preferred" in t:
        return "blue_cash_preferred"
    return None


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    request_id = new_request_id()

    msg = (req.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")

    session_id = (getattr(req, "session_id", None) or "default").strip() or "default"
    state = _get_session_state(session_id)

    # If caller provides customer_id explicitly, store it
    customer_id = getattr(req, "customer_id", None)
    if customer_id:
        state["last_customer_id"] = customer_id

    # 1) Tools
    tools_meta = await mcp.list_tools()
    tools_for_openai = _mcp_tools_to_openai_tools(
        [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools_meta]
    )

    # 2) Base system prompt + memory
    system = (
        "You are an Amex card assistant for a demo app using ONLY MCP tools and mock JSON data.\n"
        "Rules:\n"
        "- Use tools for factual details (annual fees, rewards, benefits, offers, eligibility). Never guess.\n"
        "- If a user asks a follow-up like 'annual fee?' or 'am I eligible?' and a last_card_id exists in memory, answer for that card.\n"
        "- If asked eligibility and memory has last_customer_id + last_card_id, call check_eligibility.\n"
    )

    memory_line = _render_memory(state)

    # 3) Build messages INCLUDING history (this is the key fix)
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system}, {"role": "system", "content": memory_line}]

    history = _SESSION_HISTORY.get(session_id, [])
    if history:
        messages.extend(history[-MAX_HISTORY_TURNS:])

    # 4) Light steering for follow-ups (no hard policies, just context)
    # If they ask "annual fee?" and we have last_card_id, inject a tiny hint.
    if _is_annual_fee_question(msg) and state.get("last_card_id"):
        messages.append(
            {
                "role": "system",
                "content": f"Follow-up detected: interpret this as asking the annual fee for card_id='{state['last_card_id']}'. Use tools.",
            }
        )

    if _is_eligibility_question(msg) and state.get("last_card_id") and state.get("last_customer_id"):
        messages.append(
            {
                "role": "system",
                "content": f"Follow-up detected: check eligibility using customer_id='{state['last_customer_id']}' and card_id='{state['last_card_id']}' via tools.",
            }
        )

    messages.append({"role": "user", "content": msg})

    tools_used: list[str] = []

    # 5) Tool loop
    for _ in range(8):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools_for_openai,
            tool_choice="auto",
        )

        msg_obj = resp.choices[0].message
        tool_calls = getattr(msg_obj, "tool_calls", None)

        if tool_calls:
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

                try:
                    args = json.loads(tc.function.arguments or "{}")
                    if not isinstance(args, dict):
                        args = {}
                except json.JSONDecodeError:
                    args = {}

                start = log_tool_call_start(request_id, tool_name, args)
                try:
                    tool_result = await mcp.call_tool(tool_name, args)
                    log_tool_call_end(request_id, tool_name, start, ok=True)
                except Exception as e:
                    log_tool_call_end(request_id, tool_name, start, ok=False, error=str(e))
                    raise

                _update_memory_from_tool_call(state, tool_name, args)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )
            continue

        # Final answer
        final_text = msg_obj.content or "I couldn't generate a response."

        # Store history
        _SESSION_HISTORY[session_id].append({"role": "user", "content": msg})
        _SESSION_HISTORY[session_id].append({"role": "assistant", "content": final_text})

        # Backup: infer last card from assistant response (important!)
        inferred = _infer_last_card_from_assistant_text(final_text)
        if inferred:
            state["last_card_id"] = inferred

        return ChatResponse(reply=final_text, tools_used=tools_used, suggestions=[])

    return ChatResponse(
        reply="I’m having trouble completing that request right now. Try rephrasing.",
        tools_used=tools_used,
        suggestions=[],
    )


@router.get("/history")
def history(session_id: str = "default") -> list[dict]:
    session_id = (session_id or "default").strip() or "default"
    _get_session_state(session_id)
    return _SESSION_HISTORY.get(session_id, [])


@router.post("/clear")
def clear(session_id: str = "default") -> dict:
    session_id = (session_id or "default").strip() or "default"
    _SESSION_MEMORY.pop(session_id, None)
    _SESSION_HISTORY.pop(session_id, None)
    return {"ok": True, "session_id": session_id}
