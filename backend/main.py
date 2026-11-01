"""
Pure RAG Microservice — Voice-RAG Bot (Backend 1)
==================================================
Runs on Port 8000.

Responsibilities (Backend 1 per the architecture diagram):
  - Document Ingestion & Chunking
  - Hybrid Search (dense vectors + BM25 keywords, merged with Reciprocal Rank Fusion)
  - MMR Diversity Filter
  - Strictly Grounded LLM (Zero Tools — answers from documents only)
  - STT/TTS (Sinhala & English)
  - Conversation Memory
  - Health Probe: GET /health  →  mode: "pure-rag"

The "RAG + Tools" backend runs separately on Port 8001 (tool_server.py).
Frontend selects which backend to use via the x-backend-mode header.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import PORT
from backend.security import cors_kwargs
from backend.db import init_db_schema, close_db_pool, is_db_connected, seed_initial_students
from backend.routers import auth, documents, rag, audio, memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("voicerag.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Voice-RAG Backend 1 — Pure RAG (Port %s)...", PORT)
    init_db_schema()
    seed_initial_students()
    logger.info("Backend 1 ready — Pure RAG mode active (MMR + Strictly Grounded LLM)")
    yield
    logger.info("Shutting down Backend 1 — Pure RAG Service...")
    close_db_pool()


app = FastAPI(
    title="Voice-RAG Bot — Backend 1: Pure RAG",
    description=(
        "Pure RAG backend: document ingestion, hybrid search (dense + BM25 merged with Reciprocal Rank Fusion), "
        "MMR diversity filter, and strictly grounded LLM with zero tool calls. Port 8000."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, **cors_kwargs())

# ── Routers: RAG, Audio, Documents, Memory ───────────────────────────────────
# NOTE: /api/agentic-rag, /api/students, /api/databases → served by Backend 2 (Port 8001)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(rag.router)
app.include_router(audio.router)
app.include_router(memory.router)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Voice-RAG Bot — Backend 1: Pure RAG",
        "mode": "pure-rag",
        "port": PORT,
        "docs": "/docs",
        "backend2": "http://localhost:8001 (RAG with Tools)",
    }


@app.get("/health")
def health_check():
    db_active = is_db_connected()
    return {
        "status": "healthy",
        "service": "Backend 1 — Pure RAG",
        "mode": "pure-rag",
        "port": PORT,
        "dbConnected": db_active,
        "database": "PostgreSQL + pgvector" if db_active else "In-Memory Vector Store",
        "features": [
            "document-ingestion",
            "hybrid-search-dense-bm25-rrf",
            "mmr-diversity-filter",
            "strictly-grounded-llm",
            "stt-tts",
        ],
        "backend2": "http://localhost:8001",
        "mcpServer": "http://localhost:8005/mcp/sse",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT, reload=True)
