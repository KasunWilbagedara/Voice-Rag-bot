"""
MCP Server — Voice-RAG Bot (Port 8005)
=======================================
Model Context Protocol (MCP) server that exposes all registered tools
to external AI clients (Claude Desktop, Cursor, etc.).

Transports supported:
  - SSE  (Server-Sent Events): GET  /mcp/sse   — for web-based clients
  - HTTP POST:                 POST /mcp/call  — simple JSON RPC
  - Stdio:                     run with --stdio flag for CLI clients

External clients connect to:
  SSE:   http://localhost:8005/mcp/sse
  HTTP:  http://localhost:8005/mcp/call

Usage:
  python -m backend.mcp_server          # SSE + HTTP mode (Port 8005)
  python -m backend.mcp_server --stdio  # Stdio mode (Claude Desktop)
"""

import sys
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Load tools on startup
from backend import tools as tools_module

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voicerag.mcp_server")

MCP_PORT = 8005
MCP_VERSION = "2024-11-05"
SERVER_NAME = "voice-rag-mcp-server"
SERVER_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# MCP Protocol Helpers
# ---------------------------------------------------------------------------

def _tool_to_mcp_schema(tool: Dict[str, Any]) -> Dict:
    """Converts a registry tool entry to MCP tool schema format."""
    param_names = tool.get("param_names", [])
    parameters = tool.get("parameters", {})
    return {
        "name": tool["name"],
        "description": tool["description"],
        "inputSchema": {
            "type": "object",
            "properties": {
                p: parameters.get("properties", {}).get(p, {"type": "string", "description": p})
                for p in param_names
            },
            "required": param_names,
        },
    }


def _mcp_response(id: Any, result: Any) -> Dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _mcp_error(id: Any, code: int, message: str) -> Dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def _handle_mcp_request(request_data: Dict) -> Dict:
    """Dispatch a single MCP JSON-RPC request and return a response dict."""
    method = request_data.get("method", "")
    params = request_data.get("params", {})
    req_id = request_data.get("id")

    logger.info("MCP request: method=%s id=%s", method, req_id)

    # ── initialize ────────────────────────────────────────────────────────────
    if method == "initialize":
        return _mcp_response(req_id, {
            "protocolVersion": MCP_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        })

    # ── tools/list ────────────────────────────────────────────────────────────
    elif method == "tools/list":
        all_tools = tools_module.list_tools()
        return _mcp_response(req_id, {
            "tools": [_tool_to_mcp_schema(t) for t in all_tools],
        })

    # ── tools/call ────────────────────────────────────────────────────────────
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if not tool_name:
            return _mcp_error(req_id, -32602, "Missing tool name")

        try:
            result = tools_module.call_tool(tool_name, **tool_args)
            result_text = json.dumps(result, ensure_ascii=False, default=str)
            return _mcp_response(req_id, {
                "content": [{"type": "text", "text": result_text}],
                "isError": False,
            })
        except ValueError as ve:
            return _mcp_response(req_id, {
                "content": [{"type": "text", "text": f"Tool error: {ve}"}],
                "isError": True,
            })
        except Exception as exc:
            logger.error("MCP tool call error for '%s': %s", tool_name, exc)
            return _mcp_response(req_id, {
                "content": [{"type": "text", "text": f"Tool execution failed: {exc}"}],
                "isError": True,
            })

    # ── ping ──────────────────────────────────────────────────────────────────
    elif method == "ping":
        return _mcp_response(req_id, {})

    # ── notifications (no response needed) ────────────────────────────────────
    elif method.startswith("notifications/"):
        return None  # type: ignore

    else:
        return _mcp_error(req_id, -32601, f"Method not found: {method}")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    tool_count = len(tools_module.list_tools())
    logger.info("MCP Server starting on Port %s — %d tools registered", MCP_PORT, tool_count)
    yield
    logger.info("MCP Server shutting down...")


app = FastAPI(
    title="Voice-RAG MCP Server",
    description="Model Context Protocol server — exposes all RAG tools to Claude Desktop, Cursor, and other MCP clients.",
    version=SERVER_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# SSE Transport — GET /mcp/sse
# ---------------------------------------------------------------------------

async def _sse_stream(request: Request) -> AsyncGenerator[str, None]:
    """
    SSE stream for MCP clients.
    Sends the server endpoint event on connection, then keeps the connection
    open and waits for the client to POST messages to /mcp/message.
    """
    # Send endpoint event so client knows where to POST messages
    endpoint_url = str(request.base_url) + "mcp/message"
    yield f"event: endpoint\ndata: {endpoint_url}\n\n"

    # Keep connection alive with periodic heartbeat
    try:
        while True:
            if await request.is_disconnected():
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(15)
    except asyncio.CancelledError:
        pass


@app.get("/mcp/sse")
async def mcp_sse_endpoint(request: Request):
    """SSE endpoint for MCP clients (Claude Desktop, Cursor)."""
    return StreamingResponse(
        _sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/mcp/message")
async def mcp_message_endpoint(request: Request):
    """HTTP POST endpoint for MCP JSON-RPC messages (paired with SSE)."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    response = _handle_mcp_request(body)
    if response is None:
        return {}
    return response


# ---------------------------------------------------------------------------
# Simple HTTP JSON-RPC endpoint — POST /mcp/call
# ---------------------------------------------------------------------------

class MCPCallRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}


@app.post("/mcp/call")
def mcp_call_tool(req: MCPCallRequest):
    """Simple HTTP endpoint to call any tool (no SSE required)."""
    try:
        result = tools_module.call_tool(req.tool_name, **req.parameters)
        return {"status": "success", "tool": req.tool_name, "result": result}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tool failed: {exc}")


@app.get("/mcp/tools")
def mcp_list_tools():
    """Lists all available tools in MCP schema format."""
    all_tools = tools_module.list_tools()
    return {
        "tools": [_tool_to_mcp_schema(t) for t in all_tools],
        "count": len(all_tools),
    }


@app.get("/health")
def health():
    tool_count = len(tools_module.list_tools())
    return {
        "status": "healthy",
        "service": "Voice-RAG MCP Server",
        "port": MCP_PORT,
        "protocol": MCP_VERSION,
        "toolsCount": tool_count,
        "transports": ["SSE (/mcp/sse)", "HTTP (/mcp/call)", "Stdio (--stdio flag)"],
    }


@app.get("/")
def root():
    return {
        "service": "Voice-RAG MCP Server",
        "port": MCP_PORT,
        "sse": "/mcp/sse",
        "call": "/mcp/call",
        "tools": "/mcp/tools",
        "docs": "/docs",
    }


# ---------------------------------------------------------------------------
# Stdio Transport (for Claude Desktop)
# ---------------------------------------------------------------------------

def run_stdio():
    """
    Runs MCP server in stdio mode for Claude Desktop integration.
    Reads JSON-RPC messages from stdin, writes responses to stdout.
    """
    logger.info("MCP Server running in stdio mode")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request_data = json.loads(line)
            response = _handle_mcp_request(request_data)
            if response is not None:
                print(json.dumps(response), flush=True)
        except json.JSONDecodeError as e:
            error = _mcp_error(None, -32700, f"Parse error: {e}")
            print(json.dumps(error), flush=True)
        except Exception as e:
            error = _mcp_error(None, -32603, f"Internal error: {e}")
            print(json.dumps(error), flush=True)


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--stdio" in sys.argv:
        run_stdio()
    else:
        import uvicorn
        uvicorn.run("backend.mcp_server:app", host="0.0.0.0", port=MCP_PORT, reload=False)
