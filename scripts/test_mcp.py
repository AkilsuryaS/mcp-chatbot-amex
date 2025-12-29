import asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

MCP_URL = "http://127.0.0.1:8765/mcp"

async def main():
    transport = StreamableHttpTransport(MCP_URL)
    async with Client(transport) as client:
        tools = await client.list_tools()
        print("TOOLS:", [t.name for t in tools])

        res = await client.call_tool("list_cards", {})
        # res is a CallToolResult, print as dict
        try:
            print("RAW:", res)
            print("DUMP:", res.model_dump())
        except Exception:
            print("RAW:", res)

asyncio.run(main())
