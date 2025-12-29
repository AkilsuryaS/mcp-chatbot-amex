from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]


def _to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


class MCPMockClient:
    """
    Connects to an MCP server over Streamable HTTP (recommended). :contentReference[oaicite:3]{index=3}
    """

    def __init__(self, server_url: str):
        self._transport = StreamableHttpTransport(server_url)
        self._lock = asyncio.Lock()

    async def list_tools(self) -> list[MCPTool]:
        async with self._lock:
            async with Client(self._transport) as client:
                tools = await client.list_tools()
                out: list[MCPTool] = []
                for t in tools:
                    schema = getattr(t, "inputSchema", None) or {"type": "object", "properties": {}}
                    desc = getattr(t, "description", "") or ""
                    out.append(MCPTool(name=t.name, description=desc, input_schema=schema))
                return out

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        async with self._lock:
            async with Client(self._transport) as client:
                result = await client.call_tool(name, arguments)
                return _to_jsonable(result)
