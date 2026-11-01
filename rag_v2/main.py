"""
RAG v2 — FastAPI application entry point.

Run directly:
    python -m rag_v2.main

Or via uvicorn:
    uvicorn rag_v2.main:app --host 0.0.0.0 --port 8002 --reload
"""

import importlib
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_v2.config import CORS_ORIGINS, PORT
from rag_v2.routers import documents, health, ingest, memory, query
from rag_v2.storage.db import close_db_pool, init_db_schema
from rag_v2.tools import list_tools

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool modules that register themselves via @register_tool decorators.
# They are imported here only for their side-effects.
# ---------------------------------------------------------------------------

_TOOL_MODULES = [
    "rag_v2.tools.external",
    "rag_v2.tools.sql_tools",
]


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ------------------------------------------------------------------ #
    # STARTUP
    # ------------------------------------------------------------------ #
    logger.info("=" * 60)
    logger.info("RAG v2 — starting up on port %d", PORT)
    logger.info("=" * 60)

    # Initialise database schema (creates tables / extensions if missing)
    try:
        if init_db_schema():
            logger.info("Database schema initialised successfully.")
        else:
            logger.error("Database schema initialisation failed — DB endpoints will be unavailable.")
    except Exception as exc:
        logger.error("Database schema initialisation failed: %s", exc)
        # We continue anyway so the service can still serve non-DB endpoints

    # Import tool modules to trigger @register_tool side-effects
    loaded_tool_modules: list[str] = []
    for module_path in _TOOL_MODULES:
        try:
            importlib.import_module(module_path)
            loaded_tool_modules.append(module_path)
            logger.info("Loaded tool module: %s", module_path)
        except ModuleNotFoundError:
            logger.warning("Tool module not found (skipping): %s", module_path)
        except Exception as exc:
            logger.error("Error loading tool module '%s': %s", module_path, exc)

    registered_tools = list_tools()
    logger.info(
        "Tool loading complete — %d tool(s) registered from %d module(s).",
        len(registered_tools),
        len(loaded_tool_modules),
    )
    for tool in registered_tools:
        tool_name = tool.get("name") or tool.get("function", {}).get("name", "<unknown>")
        logger.info("  • %s", tool_name)

    logger.info("RAG v2 is ready.")

    # ------------------------------------------------------------------ #
    # Hand control to the application
    # ------------------------------------------------------------------ #
    yield

    # ------------------------------------------------------------------ #
    # SHUTDOWN
    # ------------------------------------------------------------------ #
    logger.info("RAG v2 — shutting down…")
    try:
        close_db_pool()
        logger.info("Database connection pool closed.")
    except Exception as exc:
        logger.error("Error closing DB pool: %s", exc)

    logger.info("RAG v2 — shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RAG v2 — Retrieval-Augmented Generation API",
    description=(
        "Standalone RAG microservice with hybrid search, streaming, citations, "
        "tool calling and conversation memory."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(documents.router)
app.include_router(memory.router)

# ---------------------------------------------------------------------------
# Direct execution entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "rag_v2.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=True,
        log_level="info",
    )
