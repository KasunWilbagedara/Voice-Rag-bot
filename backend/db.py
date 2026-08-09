import math
import logging
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from backend.config import DATABASE_URL

logger = logging.getLogger("voicerag.db")

class InMemoryStore:
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []
        self.chat_history: List[Dict[str, Any]] = []

in_memory_store = InMemoryStore()

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
        return conn
    except Exception as e:
        logger.warning(f"Database connection failed ({e}). Fallback to in-memory store.")
        return None

def is_db_connected() -> bool:
    conn = get_db_connection()
    if conn:
        conn.close()
        return True
    return False

def init_db_schema():
    """Ensures vector extension and tables exist if database is connected."""
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    title VARCHAR(255) NOT NULL,
                    file_type VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    chunk_index INT NOT NULL,
                    embedding VECTOR,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx 
                ON document_chunks USING hnsw (embedding vector_cosine_ops);
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_query_text TEXT NOT NULL,
                    retrieved_chunks JSONB,
                    ai_response_text TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
    except Exception as e:
        logger.error(f"Error initializing DB schema: {e}")
        conn.rollback()
    finally:
        conn.close()
