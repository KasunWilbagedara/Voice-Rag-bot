import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import PORT
from backend.db import init_db_schema, close_db_pool, is_db_connected, seed_initial_students
from backend.routers import documents, rag, audio, students, databases, chat_sessions

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
    title="Voice-RAG Bot Python Backend",
    description="Full Python Backend and RAG Engine for Voice-RAG Bot (Sinhala & English)",
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

# Include API Routers
app.include_router(documents.router)
app.include_router(rag.router)
app.include_router(audio.router)
app.include_router(students.router)
app.include_router(databases.router)
app.include_router(chat_sessions.router)

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
        "dbConnected": db_active,
        "database": "PostgreSQL + pgvector" if db_active else "In-Memory Vector Store",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT, reload=True)
