import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_with_tools.config import PORT
from backend_with_tools.db import init_db_schema, close_db_pool, is_db_connected, seed_initial_students
from backend_with_tools.tools import TOOL_REGISTRY
from backend_with_tools.routers import documents, rag, audio, students, databases, memory, history

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("tools_rag.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🛠️ Initializing Voice-RAG Bot with Tools Backend (Port %s)...", PORT)
    init_db_schema()
    seed_initial_students()
    logger.info("🛠️ Tools backend initialized with %s registered tools.", len(TOOL_REGISTRY))
    yield
    logger.info("🛠️ Shutting down Voice-RAG Bot with Tools Backend...")
    close_db_pool()


app = FastAPI(
    title="Voice-RAG Bot with Tools Backend (RAG + Databases + Live Tools)",
    description="Full Advanced Voice-RAG Engine with live real-time tools, multi-database Text-to-SQL, customer tracking, and persistent session memories.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(documents.router)
app.include_router(rag.router)
app.include_router(audio.router)
app.include_router(students.router)
app.include_router(databases.router)
app.include_router(memory.router)
app.include_router(history.router)

# Mount Model Context Protocol (MCP) Server for external MCP clients over SSE
try:
    from backend_with_tools.mcp_server import create_mcp_server
    mcp_server = create_mcp_server()
    app.mount("/mcp", mcp_server.sse_app())
    logger.info("Mounted Model Context Protocol (MCP) SSE server at /mcp")
except Exception as e:
    logger.warning("Could not mount MCP SSE server: %s", e)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Voice-RAG Bot with Tools Backend",
        "mode": "rag_with_tools",
        "port": PORT,
        "tools_enabled": True,
        "tools_count": len(TOOL_REGISTRY),
        "mcp_enabled": True,
        "mcp_sse_endpoint": "/mcp/sse",
        "docs": "/docs",
    }


@app.get("/health")
@app.get("/api/health")
def health_check():
    db_active = is_db_connected()
    return {
        "status": "healthy",
        "mode": "rag_with_tools",
        "port": PORT,
        "tools_enabled": True,
        "tools": list(TOOL_REGISTRY.keys()),
        "mcp_enabled": True,
        "mcp_sse_endpoint": "/mcp/sse",
        "database": "PostgreSQL + pgvector" if db_active else "SQLite (customer_datasets.db)",
        "description": "Voice-RAG with Multi-DB SQL, Real-Time Tools, MCP Server & Persistent Memory",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_with_tools.main:app", host="0.0.0.0", port=PORT, reload=True)
