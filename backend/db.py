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
from backend.config import DATABASE_URL

logger = logging.getLogger("voicerag.db")

SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "customer_datasets.db")

class InMemoryStore:
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []
        self.chat_history: List[Dict[str, Any]] = []
        self.students: List[Dict[str, Any]] = []

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
        logger.info("PostgreSQL connection pool initialized successfully.")
        return _db_pool
    except Exception as e:
        logger.debug(f"PostgreSQL connection offline ({e}). Using persistent SQLite database store.")
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
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def init_sqlite_rag_tables():
    """Ensures persistent SQLite document & chunk storage tables exist in customer_datasets.db."""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            file_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            content TEXT NOT NULL,
            chunk_index INT NOT NULL,
            embedding TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES rag_documents(id) ON DELETE CASCADE
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_chat_history (
            id TEXT PRIMARY KEY,
            user_query_text TEXT NOT NULL,
            retrieved_chunks TEXT,
            ai_response_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_user_memories (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL DEFAULT 'default_user',
            memory_key TEXT NOT NULL,
            memory_value TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)
        conn.commit()
        conn.close()
        logger.info("Persistent SQLite RAG tables initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing SQLite RAG tables: {e}")

def init_db_schema():
    """Ensures PostgreSQL vector extension, document tables, and student table exist."""
    init_sqlite_rag_tables()
    with get_db_connection() as conn:
        if not conn:
            return

        statements = [
            "CREATE EXTENSION IF NOT EXISTS vector;",
            """
            CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title VARCHAR(255) NOT NULL,
                file_type VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS document_chunks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                chunk_index INT NOT NULL,
                embedding VECTOR,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_query_text TEXT NOT NULL,
                retrieved_chunks JSONB,
                ai_response_text TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS user_memories (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id VARCHAR(100) NOT NULL DEFAULT 'default_user',
                memory_key VARCHAR(255) NOT NULL,
                memory_value TEXT NOT NULL,
                category VARCHAR(50) DEFAULT 'general',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                department VARCHAR(100),
                gpa NUMERIC(3,2),
                enrolled_year INT,
                status VARCHAR(50) DEFAULT 'Active'
            );
            """
        ]

        for stmt in statements:
            try:
                with conn.cursor() as cur:
                    cur.execute(stmt)
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.debug(f"DB schema statement execution note: {e}")

        logger.info("PostgreSQL database schema verified successfully.")

def seed_initial_students():
    """Pre-populates sample student records into PostgreSQL and SQLite."""
    initial_data = [
        {
            "student_id": "STU1042",
            "name": "Kasun Jayasinghe",
            "email": "kasun.j@university.ac.lk",
            "department": "Computer Science & Software Engineering",
            "gpa": 3.85,
            "enrolled_year": 2022,
            "status": "Active",
        },
        {
            "student_id": "STU1001",
            "name": "Nimal Perera",
            "email": "nimal.p@university.ac.lk",
            "department": "Data Science & Artificial Intelligence",
            "gpa": 3.72,
            "enrolled_year": 2021,
            "status": "Active",
        },
        {
            "student_id": "STU1002",
            "name": "Dilani Fernando",
            "email": "dilani.f@university.ac.lk",
            "department": "Electrical & Electronic Engineering",
            "gpa": 3.91,
            "enrolled_year": 2022,
            "status": "Active",
        },
        {
            "student_id": "STU1050",
            "name": "Sarah Smith",
            "email": "sarah.s@university.ac.lk",
            "department": "Information Technology",
            "gpa": 3.65,
            "enrolled_year": 2023,
            "status": "Active",
        },
        {
            "student_id": "STU1088",
            "name": "Kavindu Wickramasinghe",
            "email": "kavindu.w@university.ac.lk",
            "department": "Cyber Security",
            "gpa": 3.78,
            "enrolled_year": 2022,
            "status": "Active",
        },
    ]

    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    for s in initial_data:
                        cur.execute(
                            """
                            INSERT INTO students (student_id, name, email, department, gpa, enrolled_year, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (student_id) DO UPDATE SET
                                name = EXCLUDED.name,
                                email = EXCLUDED.email,
                                department = EXCLUDED.department,
                                gpa = EXCLUDED.gpa,
                                enrolled_year = EXCLUDED.enrolled_year,
                                status = EXCLUDED.status;
                            """,
                            (s["student_id"], s["name"], s["email"], s["department"], s["gpa"], s["enrolled_year"], s["status"])
                        )
                    conn.commit()
                    logger.info("Sample student records seeded into PostgreSQL DB.")
            except Exception as e:
                conn.rollback()
                logger.error(f"Error seeding student records into DB: {e}")

    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            department TEXT,
            gpa REAL,
            enrolled_year INT,
            status TEXT DEFAULT 'Active'
        );
        """)
        for s in initial_data:
            cur.execute("""
            INSERT OR REPLACE INTO students (student_id, name, email, department, gpa, enrolled_year, status)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (s["student_id"], s["name"], s["email"], s["department"], s["gpa"], s["enrolled_year"], s["status"]))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"SQLite student seed note: {e}")

    in_memory_store.students = initial_data

init_sqlite_rag_tables()


# --- PERSISTENT USER MEMORY & CONTEXT HELPERS ---
import uuid
from datetime import datetime

def save_or_update_memory(
    session_id: str = "default_user",
    memory_key: str = "",
    memory_value: str = "",
    category: str = "general",
) -> Dict[str, Any]:
    """Persists a learned fact or user preference to SQLite and PostgreSQL."""
    if not memory_key or not memory_value:
        return {}

    clean_key = memory_key.strip()
    clean_val = memory_value.strip()
    mem_id = str(uuid.uuid4())
    now_iso = datetime.utcnow().isoformat() + "Z"

    # 1. SQLite
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM rag_user_memories WHERE session_id = ? AND LOWER(memory_key) = LOWER(?);",
            (session_id, clean_key),
        )
        existing = cur.fetchone()
        if existing:
            mem_id = existing[0]
            cur.execute(
                """UPDATE rag_user_memories 
                   SET memory_value = ?, category = ?, updated_at = ? 
                   WHERE id = ?;""",
                (clean_val, category, now_iso, mem_id),
            )
        else:
            cur.execute(
                """INSERT INTO rag_user_memories (id, session_id, memory_key, memory_value, category, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?);""",
                (mem_id, session_id, clean_key, clean_val, category, now_iso, now_iso),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving memory to SQLite: {e}")

    # 2. PostgreSQL
    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO user_memories (session_id, memory_key, memory_value, category, updated_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP);
                        """,
                        (session_id, clean_key, clean_val, category),
                    )
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.debug(f"PostgreSQL memory save note: {e}")

    return {
        "id": mem_id,
        "sessionId": session_id,
        "key": clean_key,
        "value": clean_val,
        "category": category,
        "updatedAt": now_iso,
    }


def get_user_memories(session_id: str = "default_user") -> List[Dict[str, Any]]:
    """Retrieves all remembered facts for a session from SQLite."""
    memories = []
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """SELECT id, session_id, memory_key, memory_value, category, created_at, updated_at
               FROM rag_user_memories
               WHERE session_id = ?
               ORDER BY updated_at DESC;""",
            (session_id,),
        )
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            memories.append({
                "id": r[0],
                "sessionId": r[1],
                "key": r[2],
                "value": r[3],
                "category": r[4],
                "createdAt": r[5],
                "updatedAt": r[6],
            })
    except Exception as e:
        logger.error(f"Error reading SQLite memories: {e}")

    return memories


def delete_memory(memory_id: str) -> bool:
    """Deletes a specific remembered fact by ID."""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM rag_user_memories WHERE id = ?;", (memory_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        return False


def clear_all_memories(session_id: str = "default_user") -> bool:
    """Clears all stored memories for a session."""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM rag_user_memories WHERE session_id = ?;", (session_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error clearing memories: {e}")
        return False


def get_saved_chat_history(limit: int = 30) -> List[Dict[str, Any]]:
    """Retrieves saved chat conversation history across sessions from SQLite."""
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
        logger.error(f"Error fetching saved chat history: {e}")

    return history


def clear_saved_chat_history() -> bool:
    """Clears persistent chat history."""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM rag_chat_history;")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        return False
