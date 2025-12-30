from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

logger = logging.getLogger("amex-tooling")

SENSITIVE_KEYS = {"api_key", "authorization", "password", "token", "secret"}

def _redact(obj:Any) -> Any:
    """ Redact sensitive information from logs. """
    if isinstance(obj, dict):
        out = {}
        for k,v in obj.items():
            if str(k).lower() in SENSITIVE_KEYS:
                out[k] = "**REDACTED**"
            else:
                out[k] = _redact(v)
        return out
    
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    
    return obj

def log_tool_call_start(request_id:str, tool_name:str, args: dict[str, Any]) -> float:
    """ Log start & return start time. """
    start = time.perf_counter()
    payload = {
     "event": "tool_call_start",
        "request_id": request_id,
        "tool_name": tool_name,
        "args": _redact(args),   
    }

    logger.info(json.dumps(payload, ensure_ascii=False))
    return start

def log_tool_call_end(request_id:str, tool_name:str, start:float,ok:bool, error: str | None = None,) -> None:
    duration_ms = int((time.perf_counter()-start)*1000)
    payload = {
        "event": "tool_call_end",
        "request_id": request_id,
        "tool_name": tool_name,
        "duration_ms": duration_ms,
        "status": "ok" if ok else "error",
    }
    if error:
        payload["error"] = error
    logger.info(json.dumps(payload, ensure_ascii=False))

def new_request_id() -> str:
    return uuid.uuid4().hex
