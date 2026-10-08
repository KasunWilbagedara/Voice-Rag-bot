import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_pure_rag.config import PORT
from backend_pure_rag.db import init_db_schema, close_db_pool, is_db_connected
from backend_pure_rag.routers import documents, rag, audio, history

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pure_rag.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("⚡ Initializing Pure Voice-RAG Backend (Document RAG & AI Only - Port %s)...", PORT)
    init_db_schema()
    yield
    logger.info("⚡ Shutting down Pure Voice-RAG Backend...")
    close_db_pool()


app = FastAPI(
    title="Pure Voice-RAG Backend (Document RAG & AI Only)",
    description="Dedicated Pure RAG Engine: PDF/Doc parsing, hybrid vector retrieval, and pure LLM answer generation without external tools.",
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
app.include_router(history.router)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Pure Voice-RAG Backend (Document RAG & AI Only)",
        "mode": "pure_rag",
        "port": PORT,
        "tools_enabled": False,
        "docs": "/docs",
    }


@app.get("/health")
@app.get("/api/health")
def health_check():
    db_active = is_db_connected()
    return {
        "status": "healthy",
        "mode": "pure_rag",
        "port": PORT,
        "tools_enabled": False,
        "database": "PostgreSQL + pgvector" if db_active else "SQLite (pure_rag.db)",
        "description": "Pure Document RAG & AI Only (No Tools)",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_pure_rag.main:app", host="0.0.0.0", port=PORT, reload=True)
