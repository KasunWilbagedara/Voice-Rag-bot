import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import PORT
from backend.db import init_db_schema, is_db_connected
from backend.routers import documents, rag, audio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("voicerag.main")

app = FastAPI(
    title="Voice-RAG Bot Python Backend",
    description="Full Python Backend and RAG Engine for Voice-RAG Bot (Sinhala & English)",
    version="1.0.0"
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

@app.on_event("startup")
def on_startup():
    logger.info("Initializing Python Voice-RAG Backend...")
    init_db_schema()

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
