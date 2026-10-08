import os
import math
import json
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

from backend_pure_rag.config import DATABASE_URL, SQLITE_DB_PATH

logger = logging.getLogger("pure_rag.db")


class InMemoryStore:
    """In-memory fallback store when PostgreSQL or SQLite are unavailable."""
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []
        self.chat_history: List[Dict[str, Any]] = []

in_memory_store = InMemoryStore()

_db_pool: Optional[ThreadedConnectionPool] = None
_db_pool_checked: bool = False


def init_db_pool(minconn: int = 1, maxconn: int = 10, force: bool = False) -> Optional[ThreadedConnectionPool]:
    global _db_pool, _db_pool_checked
    if _db_pool is not None and not _db_pool.closed:
        return _db_pool
    if _db_pool_checked and not force:
        return None

    _db_pool_checked = True
    try:
        _db_pool = ThreadedConnectionPool(minconn, maxconn, DATABASE_URL, connect_timeout=1)
        logger.info("PostgreSQL connection pool initialized for Pure RAG.")
        return _db_pool
    except Exception as e:
        logger.debug(f"PostgreSQL connection offline ({e}). Using persistent SQLite pure_rag.db.")
        _db_pool = None
        return None


def close_db_pool():
    global _db_pool, _db_pool_checked
    if _db_pool is not None and not _db_pool.closed:
        _db_pool.closeall()
        logger.info("Database connection pool closed.")
        _db_pool = None
    _db_pool_checked = False


@contextmanager
def get_db_connection():
    global _db_pool
    conn = None
    if _db_pool is None and not _db_pool_checked:
        init_db_pool()

    if _db_pool is not None and not _db_pool.closed:
        try:
            conn = _db_pool.getconn()
        except Exception as e:
            logger.debug(f"Failed to checkout connection from pool ({e}).")
            conn = None

    try:
        yield conn
    finally:
        if conn and _db_pool and not _db_pool.closed:
            try:
                _db_pool.putconn(conn)
            except Exception as e:
                logger.debug(f"Failed to return connection to pool ({e}).")


def is_db_connected() -> bool:
    with get_db_connection() as conn:
        return conn is not None


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    # Align dimensions gracefully if vector lengths differ
    if len(vec_a) != len(vec_b):
        min_len = min(len(vec_a), len(vec_b))
        vec_a = vec_a[:min_len]
        vec_b = vec_b[:min_len]
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def init_sqlite_rag_tables():
    """Ensures persistent SQLite document & chunk storage tables exist in pure_rag.db."""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            file_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES rag_documents(id) ON DELETE CASCADE
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_chat_history (
            id TEXT PRIMARY KEY,
            user_query_text TEXT NOT NULL,
            retrieved_chunks TEXT,
            ai_response_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pure_rag_chunks_doc ON rag_document_chunks(document_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pure_rag_history_date ON rag_chat_history(created_at DESC);")
        conn.commit()
        conn.close()
        logger.info(f"Initialized Pure RAG SQLite tables in {SQLITE_DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize SQLite Pure RAG tables: {e}")

# Ensure SQLite tables exist upon module import
try:
    init_sqlite_rag_tables()
except Exception as e:
    logger.debug(f"Module load SQLite init warning: {e}")


def init_db_schema():
    """Initializes tables in PostgreSQL (if connected) and SQLite pure_rag.db."""
    init_sqlite_rag_tables()

    with get_db_connection() as conn:
        if not conn:
            logger.info("Using SQLite pure_rag.db & in-memory store for Pure RAG.")
            return

        try:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    title TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                    chunk_index INT NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(768),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
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
                cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_hnsw 
                ON document_chunks USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
                """)
                conn.commit()
                logger.info("PostgreSQL pgvector schema initialized for Pure RAG.")
        except Exception as e:
            conn.rollback()
            logger.warning(f"PostgreSQL initialization note: {e}")


def get_saved_chat_history(limit: int = 30) -> List[Dict[str, Any]]:
    """Retrieves saved chat conversation history from pure_rag.db."""
    history = []
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """SELECT id, user_query_text, retrieved_chunks, ai_response_text, created_at
               FROM rag_chat_history
               ORDER BY created_at DESC
               LIMIT ?;""",
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            chunks = []
            try:
                if r[2]:
                    chunks = json.loads(r[2])
            except Exception:
                pass

            history.append({
                "id": r[0],
                "userQuery": r[1],
                "retrievedChunks": chunks,
                "aiResponse": r[3],
                "createdAt": r[4],
            })
    except Exception as e:
        logger.error(f"Error fetching saved Pure RAG chat history: {e}")

    return history


def clear_saved_chat_history() -> bool:
    """Clears persistent chat history from pure_rag.db."""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM rag_chat_history;")
        conn.commit()
        conn.close()
        in_memory_store.chat_history.clear()
        return True
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        return False
