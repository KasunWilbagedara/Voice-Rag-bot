import math
import logging
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from backend.config import DATABASE_URL

logger = logging.getLogger("voicerag.db")

class InMemoryStore:
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []
        self.chat_history: List[Dict[str, Any]] = []
        self.students: List[Dict[str, Any]] = []

in_memory_store = InMemoryStore()

_db_pool: Optional[ThreadedConnectionPool] = None

def init_db_pool(minconn: int = 1, maxconn: int = 10) -> Optional[ThreadedConnectionPool]:
    global _db_pool
    if _db_pool is not None and not _db_pool.closed:
        return _db_pool
    try:
        _db_pool = ThreadedConnectionPool(minconn, maxconn, DATABASE_URL, connect_timeout=3)
        logger.info("Database connection pool initialized successfully.")
        return _db_pool
    except Exception as e:
        logger.warning(f"Database connection pool initialization failed ({e}). Fallback to in-memory store.")
        _db_pool = None
        return None

def close_db_pool():
    global _db_pool
    if _db_pool is not None and not _db_pool.closed:
        _db_pool.closeall()
        logger.info("Database connection pool closed.")
        _db_pool = None

@contextmanager
def get_db_connection():
    global _db_pool
    conn = None
    if _db_pool is None or _db_pool.closed:
        init_db_pool()

    if _db_pool is not None and not _db_pool.closed:
        try:
            conn = _db_pool.getconn()
        except Exception as e:
            logger.warning(f"Failed to checkout connection from pool ({e}).")
            conn = None

    try:
        yield conn
    finally:
        if conn and _db_pool and not _db_pool.closed:
            try:
                _db_pool.putconn(conn)
            except Exception as e:
                logger.warning(f"Failed to return connection to pool ({e}).")

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

def init_db_schema():
    """Ensures vector extension, document tables, and student database table exist."""
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

        logger.info("Database schema initialized successfully.")

def seed_initial_students():
    """Pre-populates sample student records into PostgreSQL or InMemoryStore."""
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
        else:
            in_memory_store.students = initial_data
            logger.info("Sample student records seeded into In-Memory Store.")

