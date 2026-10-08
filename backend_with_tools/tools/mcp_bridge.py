"""
Model Context Protocol (MCP) Client Bridge.

Allows Voice-RAG Bot to connect to external MCP servers (via SSE or stdio)
and import their tools dynamically into the central TOOL_REGISTRY.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("voicerag.tools.mcp_bridge")

try:
    from mcp.client.session import ClientSession
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    MCP_CLIENT_AVAILABLE = True
except ImportError:
    MCP_CLIENT_AVAILABLE = False


class MCPBridge:
    """
    Client bridge that connects to an external MCP Server and exposes its tools
    to the Voice-RAG application.
    """

    def __init__(self, server_url: Optional[str] = None):
        self.server_url = server_url
        self.discovered_tools: List[Dict[str, Any]] = []

    async def list_remote_tools(self, sse_url: str) -> List[Dict[str, Any]]:
        """
        Connects to an external MCP SSE server and queries available tools.
        """
        if not MCP_CLIENT_AVAILABLE:
            raise ImportError("mcp package is required for MCPBridge. Run: pip install mcp")

        tools_list = []
        try:
            async with sse_client(sse_url) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    response = await session.list_tools()
                    for t in response.tools:
                        tools_list.append({
                            "name": t.name,
                            "description": t.description or "External MCP Tool",
                            "input_schema": getattr(t, "inputSchema", {}),
                        })
            self.discovered_tools = tools_list
            logger.info(f"Discovered {len(tools_list)} tools from remote MCP Server at {sse_url}")
            return tools_list
        except Exception as e:
            logger.error(f"Error fetching tools from remote MCP server ({sse_url}): {e}")
            return []

    async def execute_remote_tool(self, sse_url: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Executes a tool on an external MCP server over SSE.
        """
        if not MCP_CLIENT_AVAILABLE:
            raise ImportError("mcp package is required for MCPBridge.")

        try:
            async with sse_client(sse_url) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return result
        except Exception as e:
            logger.error(f"Error executing remote MCP tool '{tool_name}': {e}")
            raise
