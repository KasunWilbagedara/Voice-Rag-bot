"""
Tool Execution + Agentic RAG Microservice — Voice-RAG Bot (Backend 2)
======================================================================
Runs on Port 8001 (TOOL_PORT).

Responsibilities (Backend 2 per the architecture diagram):
  - Agentic LLM Reasoner: POST /api/agentic-rag
  - Tool Registry:        GET  /api/tools   |  POST /api/tools/call
  - STT/TTS + Prosody:   mounted from routers/audio.py
  - Database Management: mounted from routers/databases.py
  - Student Records:     mounted from routers/students.py
  - Session Memory:      mounted from routers/memory.py
  - Health Probe:        GET  /health  →  mode: "rag-with-tools"
  - MCP info:            GET  /mcp     →  points to Port 8005

This service is the "RAG + Tools" backend in the mode switcher.
The "Pure RAG" backend is backend/main.py on Port 8000.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import TOOL_PORT
from backend.db import init_db_schema, close_db_pool, seed_initial_students, is_db_connected
from backend import tools
from backend.routers import databases, students, audio, memory, agentic_rag

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voicerag.tool_server")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Voice-RAG Backend 2 — RAG + Tools (Port %s)...", TOOL_PORT)
    init_db_schema()
    seed_initial_students()
    registered = [t["name"] for t in tools.list_tools()]
    logger.info("Tool registry loaded — %d tools: %s", len(registered), registered)
    yield
    logger.info("Shutting down Backend 2 — RAG + Tools Service...")
    close_db_pool()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Voice-RAG Backend 2 — RAG with Tools",
    description=(
        "Full-featured RAG + Agentic LLM + Tool Registry + STT/TTS service. "
        "Runs on Port 8001. Pairs with the Pure RAG backend on Port 8000."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Agentic RAG (multi-step LLM reasoning + tools) ──────────────────────────
app.include_router(agentic_rag.router)

# ── STT / TTS (audio transcription and synthesis) ───────────────────────────
app.include_router(audio.router)

# ── Database & Student management ───────────────────────────────────────────
app.include_router(databases.router)
app.include_router(students.router)

# ── Session memory ───────────────────────────────────────────────────────────
app.include_router(memory.router)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ToolCallRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Voice-RAG Backend 2 — RAG with Tools",
        "port": TOOL_PORT,
        "mode": "rag-with-tools",
        "docs": "/docs",
        "agentic_rag": "/api/agentic-rag",
        "tools": "/api/tools",
        "mcp_server": f"http://localhost:8005/mcp/sse",
    }


@app.get("/health")
def health_check():
    """Liveness probe — returns service mode and tool count."""
    db_active = is_db_connected()
    registered_tools = tools.list_tools()
    return {
        "status": "healthy",
        "service": "Backend 2 — RAG with Tools",
        "mode": "rag-with-tools",
        "port": TOOL_PORT,
        "dbConnected": db_active,
        "database": "PostgreSQL + pgvector" if db_active else "In-Memory",
        "toolsCount": len(registered_tools),
        "features": [
            "agentic-llm-reasoner",
            "tool-registry",
            "stt-tts",
            "session-memory",
            "hybrid-search",
        ],
        "mcpServer": "http://localhost:8005/mcp/sse",
    }


@app.get("/mcp")
def mcp_info():
    """Returns MCP Server connection info for external clients (Claude Desktop, Cursor)."""
    return {
        "mcpServer": {
            "sse_url": "http://localhost:8005/mcp/sse",
            "stdio_command": "python -m backend.mcp_server --stdio",
            "supported_clients": ["Claude Desktop", "Cursor", "Any MCP-compatible client"],
            "tools_count": len(tools.list_tools()),
        }
    }


@app.get("/api/tools")
def list_all_tools():
    """Returns full JSON metadata for every registered tool."""
    tool_list = tools.list_tools()
    return {"tools": tool_list, "count": len(tool_list)}


@app.post("/api/tools/call")
def call_tool_endpoint(req: ToolCallRequest):
    """
    Execute any registered tool by name with arbitrary keyword parameters.

    Request body:
        {
            "tool_name": "get_live_weather",
            "parameters": {"city": "Colombo"}
        }
    """
    if not req.tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required.")

    registered_names = [t["name"] for t in tools.list_tools()]
    if req.tool_name not in registered_names:
        raise HTTPException(
            status_code=400,
            detail=f"Tool '{req.tool_name}' not found. Available: {registered_names}",
        )

    try:
        result = tools.call_tool(req.tool_name, **req.parameters)
        return {"status": "success", "result": result}
    except TypeError as te:
        logger.error("Invalid parameters for tool '%s': %s", req.tool_name, te)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters for tool '{req.tool_name}': {te}",
        )
    except Exception as exc:
        logger.error("Tool execution error for '%s': %s", req.tool_name, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Tool execution failed for '{req.tool_name}': {exc}",
        )


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.tool_server:app", host="0.0.0.0", port=TOOL_PORT, reload=True)
