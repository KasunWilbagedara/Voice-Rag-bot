"""
rag_v2/storage/db.py
--------------------
PostgreSQL + pgvector connection pool, schema initialisation, and helpers.
"""

import logging
import threading
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extensions import connection as PgConnection

from rag_v2.config import DATABASE_URL

logger = logging.getLogger("rag_v2.storage.db")

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_pool: Optional[pg_pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Pool lifecycle
# ---------------------------------------------------------------------------


def init_db_pool() -> None:
    """Initialise the shared ThreadedConnectionPool (min=1, max=10).

    Safe to call multiple times — subsequent calls are no-ops if the pool
    is already alive.
    """
    global _pool

    with _pool_lock:
        if _pool is not None and not _pool.closed:
            logger.debug("DB pool already initialised — skipping.")
            return

        try:
            _pool = pg_pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=DATABASE_URL,
                connect_timeout=2,
            )
            logger.info("PostgreSQL connection pool created (min=1, max=10).")
        except psycopg2.OperationalError as exc:
            logger.error("Failed to create DB pool: %s", exc)
            _pool = None


def close_db_pool() -> None:
    """Close all connections in the pool gracefully."""
    global _pool

    with _pool_lock:
        if _pool is not None and not _pool.closed:
            _pool.closeall()
            logger.info("PostgreSQL connection pool closed.")
        _pool = None


# ---------------------------------------------------------------------------
# Connection context manager
# ---------------------------------------------------------------------------


@contextmanager
def get_db_connection() -> Generator[Optional[PgConnection], None, None]:
    """Yield a psycopg2 connection from the pool, or *None* if unavailable.

    The connection is automatically returned to the pool (or closed on error)
    when the ``with`` block exits.

    Usage::

        with get_db_connection() as conn:
            if conn is None:
                ...  # DB unavailable
            else:
                with conn.cursor() as cur:
                    cur.execute(...)
                conn.commit()
    """
    if _pool is None or _pool.closed:
        # Attempt a lazy initialisation so callers don't have to worry about
        # startup order.
        init_db_pool()

    conn: Optional[PgConnection] = None
    try:
        if _pool is not None and not _pool.closed:
            conn = _pool.getconn()
        yield conn
    except psycopg2.OperationalError as exc:
        logger.error("DB operational error: %s", exc)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
            _pool.putconn(conn, close=True)
            conn = None
        yield None  # type: ignore[misc]
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn is not None and _pool is not None and not _pool.closed:
            _pool.putconn(conn)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def is_db_connected() -> bool:
    """Return *True* if the database is reachable, *False* otherwise."""
    try:
        with get_db_connection() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            return True
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

_DDL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table: one row per ingested document
CREATE TABLE IF NOT EXISTS rag_v2_documents (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    file_type   TEXT,
    source_url  TEXT,
    file_size   INTEGER,
    chunk_count INTEGER,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Chunks table: one row per text chunk with its embedding
CREATE TABLE IF NOT EXISTS rag_v2_chunks (
    id          TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES rag_v2_documents(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    chunk_index INTEGER,
    embedding   vector(768),
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Chat history table: one row per conversational turn
CREATE TABLE IF NOT EXISTS rag_v2_chat_history (
    id         SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast approximate nearest-neighbour search (cosine)
CREATE INDEX IF NOT EXISTS idx_rag_v2_chunks_hnsw
    ON rag_v2_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- B-tree index to speed up chunk lookups by document
CREATE INDEX IF NOT EXISTS idx_rag_v2_chunks_doc_id
    ON rag_v2_chunks (document_id);

-- Composite index to speed up conversation history retrieval in order
CREATE INDEX IF NOT EXISTS idx_rag_v2_history_session
    ON rag_v2_chat_history (session_id, created_at);
"""


def init_db_schema() -> bool:
    """Create all rag_v2_* tables and indexes if they do not already exist.

    Returns *True* on success, *False* if the database is unreachable or the
    DDL fails.
    """
    # Ensure the pool exists before we attempt anything.
    if _pool is None or _pool.closed:
        init_db_pool()

    try:
        with get_db_connection() as conn:
            if conn is None:
                logger.error(
                    "Cannot initialise schema — database connection unavailable."
                )
                return False

            with conn.cursor() as cur:
                cur.execute(_DDL)
            conn.commit()
            logger.info("rag_v2 database schema initialised successfully.")
            return True

    except psycopg2.Error as exc:
        logger.error("Schema initialisation failed: %s", exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error during schema init: %s", exc)
        return False
