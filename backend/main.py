import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import PORT
from backend.db import init_db_schema, close_db_pool, is_db_connected, seed_initial_students
from backend.routers import documents, rag, audio, memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("voicerag.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Python Voice-RAG Backend...")
    init_db_schema()
    seed_initial_students()
    yield
    logger.info("Shutting down Python Voice-RAG Backend...")
    close_db_pool()

app = FastAPI(
    title="Voice-RAG Bot — RAG & Audio Service",
    description="RAG Engine, Vector Search, Audio STT/TTS and LLM Reasoning (Port 8000)",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for Next.js frontend demonstration UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers — RAG, Audio, Documents, and Memory
# NOTE: /api/students and /api/databases are served by the Tool Service (port 8001)
app.include_router(documents.router)
app.include_router(rag.router)
app.include_router(audio.router)
app.include_router(memory.router)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Voice-RAG Bot Python Backend API",
        "docs": "/docs",
    }

@app.get("/health")
def health_check():
    db_active = is_db_connected()
    return {
        "status": "healthy",
        "service": "RAG & Audio Service",
        "port": PORT,
        "dbConnected": db_active,
        "database": "PostgreSQL + pgvector" if db_active else "In-Memory Vector Store",
        "toolServiceUrl": "http://localhost:8001 (tool-service)",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT, reload=True)
