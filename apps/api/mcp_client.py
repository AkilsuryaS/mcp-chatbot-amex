from __future__ import annotations

from typing import Any, Dict, Optional

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


class MCPMockClient:
    """
    Minimal MCP client wrapper that talks to FastMCP over Streamable HTTP.

    MCP_SERVER_URL must look like:
      http://mcp:8765/mcp        (in docker)
      http://127.0.0.1:8765/mcp  (local)
    """

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self._transport = StreamableHttpTransport(self.server_url)

    async def list_tools(self):
        async with Client(self._transport) as client:
            return await client.list_tools()

    def _to_jsonable(self, obj: Any) -> Any:
        """
        Convert FastMCP/Pydantic objects into plain JSON-serializable Python.
        """
        if obj is None:
            return None

        # Pydantic v2 models
        if hasattr(obj, "model_dump"):
            return obj.model_dump()

        # If it's already jsonable
        if isinstance(obj, (dict, list, str, int, float, bool)):
            return obj

        # Fallback: try __dict__ (not always safe, but better than crashing)
        try:
            return dict(obj.__dict__)
        except Exception:
            return str(obj)

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        arguments = arguments or {}
        async with Client(self._transport) as client:
            res = await client.call_tool(name, arguments)

            # Ensure JSONable
            dumped = self._to_jsonable(res)

            # FastMCP often returns:
            # {"structured_content": {"result": ...}, ...}
            if isinstance(dumped, dict):
                structured = dumped.get("structured_content") or dumped.get("structuredContent") or {}
                if isinstance(structured, dict) and "result" in structured:
                    return structured["result"]

            return dumped
