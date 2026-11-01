"""
RAG v2 — Configuration & Environment
======================================
Loads .env.local then .env from the project root.
All settings can be overridden via environment variables.
"""

import os
from dotenv import load_dotenv

# Load environment files from project root (one level up from rag_v2/)
_root = os.path.join(os.path.dirname(__file__), "..")
load_dotenv(dotenv_path=os.path.join(_root, ".env.local"))
load_dotenv(dotenv_path=os.path.join(_root, ".env"))

# ── LLM / Embedding API Keys ─────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# ── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    os.getenv("POSTGRES_URL", "postgresql://postgres:postgrespassword@localhost:5432/voicerag"),
)

# ── Service Port ─────────────────────────────────────────────────────────────
PORT: int = int(os.getenv("RAG_V2_PORT", "8002"))

# ── Embedding Settings ───────────────────────────────────────────────────────
GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
# Both providers are asked for this many dimensions so every vector fits the
# rag_v2_chunks.embedding vector(768) column regardless of which key is active.
EMBEDDING_DIM: int = 768

# ── Generation models ────────────────────────────────────────────────────────
GEMINI_MODEL: str = os.getenv("RAG_V2_GEMINI_MODEL", "gemini-3.5-flash")
OPENAI_MODEL: str = os.getenv("RAG_V2_OPENAI_MODEL", "gpt-4o")

# ── Chunking Settings ────────────────────────────────────────────────────────
CHUNK_TARGET_SIZE: int = int(os.getenv("CHUNK_TARGET_SIZE", "600"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

# ── Retrieval Settings ───────────────────────────────────────────────────────
RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "10"))   # candidates before rerank
RERANK_TOP_N: int = int(os.getenv("RERANK_TOP_N", "4"))           # final chunks for prompt

# ── CORS (comma-separated browser origins allowed to call this service) ─────
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

# ── DB Table Prefix (keeps v2 tables separate from existing v1 tables) ───────
TABLE_PREFIX: str = "rag_v2"


def get_api_key(custom_key: str = None) -> str:
    """Returns the best available API key. Raises if none found."""
    key = custom_key or GEMINI_API_KEY or OPENAI_API_KEY
    if not key:
        raise ValueError(
            "No API key found. Set GEMINI_API_KEY or OPENAI_API_KEY in your .env file."
        )
    return key


def is_gemini_key(key: str = None) -> bool:
    """Returns True if the key is a Google Gemini key."""
    api_key = key or GEMINI_API_KEY or OPENAI_API_KEY or ""
    if not api_key:
        return False
    return api_key.startswith("AIza") or api_key.startswith("AQ.") or not api_key.startswith("sk-")


def get_provider(custom_key: str = None) -> str:
    """Returns 'gemini' or 'openai' based on the active key."""
    return "gemini" if is_gemini_key(custom_key) else "openai"
