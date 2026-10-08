"""
Official Model Context Protocol (MCP) Server for Voice-RAG Bot.

Exposes all Voice-RAG tools (Weather, Calculator, Web Search, Orders, Support Tickets,
Student Database, Safe SQL, Session Memory, and Knowledge Search) over the standard
Model Context Protocol (MCP).

Compatible with:
- Claude Desktop
- Cursor IDE
- Antigravity IDE & AI Agents
- Remote MCP Clients over SSE / HTTP

Usage:
    # Standard I/O mode (default for Claude Desktop / Cursor):
    python -m backend_with_tools.mcp_server

    # Server-Sent Events (SSE) HTTP mode on port 8005:
    python -m backend_with_tools.mcp_server --transport sse --port 8005
"""

import sys
import argparse
import logging
from typing import Optional

from mcp.server.mcpserver import MCPServer
from backend_with_tools.tools import TOOL_REGISTRY

# Configure logging to stderr so stdio JSON-RPC transport remains clean
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("voicerag.mcp_server")


def create_mcp_server() -> MCPServer:
    """
    Creates and configures an MCP Server instance populated with all Voice-RAG tools.
    """
    server = MCPServer(
        name="VoiceRAG-Tools-Server",
        version="1.0.0",
        instructions=(
            "Voice-RAG Bot MCP Server provides tools for real-time weather, safe math evaluation, "
            "live web search, customer order/ticket tracking, student academic lookup, "
            "read-only database SQL querying, persistent user memory, and document vector search."
        ),
    )

    registered_count = 0
    for name, entry in TOOL_REGISTRY.items():
        try:
            server.add_tool(
                entry["func"],
                name=name,
                description=entry["description"],
            )
            registered_count += 1
        except Exception as e:
            logger.warning(f"Could not register tool '{name}' to MCP Server: {e}")

    logger.info(f"Initialized VoiceRAG MCP Server with {registered_count} tools.")
    return server


def main():
    parser = argparse.ArgumentParser(description="Voice-RAG Model Context Protocol (MCP) Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP Transport protocol: 'stdio' for desktop apps/IDEs (default), or 'sse' for HTTP streaming.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host interface for SSE transport (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8005, help="Port for SSE transport (default: 8005)")

    args = parser.parse_args()
    server = create_mcp_server()

    if args.transport == "stdio":
        logger.info("Starting VoiceRAG MCP Server in stdio mode...")
        server.run(transport="stdio")
    elif args.transport == "sse":
        logger.info(f"Starting VoiceRAG MCP Server in SSE mode on http://{args.host}:{args.port}/sse ...")
        server.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
