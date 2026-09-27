"""
Tool Execution Microservice — Voice-RAG Bot
============================================
Runs on Port 8001 (TOOL_PORT).

Responsibilities:
  - Host the central TOOL_REGISTRY (tools.py)
  - Expose GET  /api/tools           → list all registered tool metadata
  - Expose POST /api/tools/call      → execute any tool by name + parameters
  - Mount /api/databases and /api/students routers
  - Expose GET  /health              → service liveness probe

This service is intentionally decoupled from RAG / audio / vector-search logic.
The RAG service (main.py, port 8000) delegates tool execution here via HTTP.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import TOOL_PORT
from backend.db import init_db_schema, close_db_pool, seed_initial_students
from backend import tools
from backend.routers import databases, students

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voicerag.tool_server")


# ---------------------------------------------------------------------------
# Lifespan: initialise shared DB schema & seed data on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Voice-RAG Tool Execution Service (Port %s)...", TOOL_PORT)
    init_db_schema()
    seed_initial_students()
    registered = [t["name"] for t in tools.list_tools()]
    logger.info("Tool registry loaded — %d tools: %s", len(registered), registered)
    yield
    logger.info("Shutting down Tool Execution Service...")
    close_db_pool()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Voice-RAG Tool Execution Service",
    description=(
        "Microservice hosting the central tool registry — "
        "SQL execution, external API tools, student/database management."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount existing database & student management routers
app.include_router(databases.router)
app.include_router(students.router)


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
        "service": "Voice-RAG Tool Execution Service",
        "port": TOOL_PORT,
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """Liveness probe — returns tool count so orchestrators can verify readiness."""
    registered_tools = tools.list_tools()
    return {
        "status": "healthy",
        "service": "Tool Service",
        "port": TOOL_PORT,
        "toolsCount": len(registered_tools),
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

    Returns:
        {
            "status": "success",
            "result": { ... }
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
# Entry-point (local development)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.tool_server:app", host="0.0.0.0", port=TOOL_PORT, reload=True)
