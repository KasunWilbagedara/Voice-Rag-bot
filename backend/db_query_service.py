import re
import os
import io
import csv
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager

import pandas as pd

from backend.db import get_db_connection, in_memory_store, is_db_connected

logger = logging.getLogger("voicerag.db_query_service")

# --- MULTI-DATABASE CONNECTION MANAGER ---
class DatabaseManager:
    def __init__(self):
        # Stores registered databases: {db_id: {name, type, uri_or_path, connection_type, created_at, tables}}
        self.databases: Dict[str, Dict[str, Any]] = {}
        # Path to local SQLite file for dynamic customer datasets
        self.sqlite_db_path = os.path.join(os.path.dirname(__file__), "customer_datasets.db")
        self._init_customer_datasets_sqlite()

    def _init_customer_datasets_sqlite(self):
        """Initializes built-in Customer Support SQLite database with sample tables."""
        try:
            conn = sqlite3.connect(self.sqlite_db_path)
            cur = conn.cursor()
            
            # 1. Customers Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                tier TEXT DEFAULT 'Standard',
                status TEXT DEFAULT 'Active',
                total_spent REAL DEFAULT 0.0
            );
            """)

            # 2. Orders Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT,
                product_name TEXT,
                amount REAL,
                status TEXT,
                order_date TEXT
            );
            """)

            # 3. Support Tickets Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id TEXT PRIMARY KEY,
                customer_name TEXT,
                issue_category TEXT,
                description TEXT,
                resolution_status TEXT,
                priority TEXT
            );
            """)

            # 4. Products & FAQ Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS products_faq (
                item_id TEXT PRIMARY KEY,
                product_or_topic TEXT,
                common_question TEXT,
                official_policy_answer TEXT,
                category TEXT
            );
            """)

            # Seed sample data if empty
            cur.execute("SELECT COUNT(*) FROM customers;")
            if cur.fetchone()[0] == 0:
                cur.executemany(
                    "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?);",
                    [
                        ("CUST-101", "Amara Perera", "amara.p@example.lk", "VIP Premium", "Active", 145000.0),
                        ("CUST-102", "Ruwan Fernando", "ruwan.f@example.lk", "Gold", "Active", 82000.0),
                        ("CUST-103", "Dilini Silva", "dilini.s@example.lk", "Standard", "Active", 23500.0),
                    ]
                )
                cur.executemany(
                    "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?);",
                    [
                        ("ORD-9021", "CUST-101", "Voice AI Router Enterprise Package", 45000.0, "Delivered", "2026-08-01"),
                        ("ORD-9022", "CUST-102", "Smart Customer Bot Add-on", 18500.0, "Processing", "2026-08-10"),
                        ("ORD-9023", "CUST-101", "Cloud Vector Storage Expansion", 12000.0, "Shipped", "2026-08-11"),
                    ]
                )
                cur.executemany(
                    "INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?);",
                    [
                        ("TCK-5501", "Amara Perera", "API Integration", "Needs assistance setting up custom webhook for Voice RAG", "In Progress", "High"),
                        ("TCK-5502", "Ruwan Fernando", "Billing Inquiry", "Requesting VAT invoice for Order ORD-9022", "Resolved", "Medium"),
                    ]
                )
                cur.executemany(
                    "INSERT INTO products_faq VALUES (?, ?, ?, ?, ?);",
                    [
                        ("FAQ-1", "Refund Policy", "What is the refund period for Voice RAG Bot subscriptions?", "Refunds are processed within 14 business days of submission upon approval by support.", "Billing"),
                        ("FAQ-2", "Supported Audio Formats", "Which audio input formats are accepted by the bot?", "The bot accepts WAV, MP3, M4A, WEBM, and OGG audio streams for real-time speech recognition.", "Technical"),
                    ]
                )
                conn.commit()

            conn.close()
            logger.info("Initialized local Customer Datasets SQLite database successfully.")

            # Register SQLite database in manager
            self.databases["customer_support_db"] = {
                "id": "customer_support_db",
                "name": "Customer Support Datasets (SQLite)",
                "type": "sqlite",
                "uri_or_path": self.sqlite_db_path,
                "is_builtin": True,
            }
        except Exception as e:
            logger.error(f"Error initializing SQLite customer datasets: {e}")

    def reseed_sample_data(self) -> Dict[str, Any]:
        """Clears existing rows and reseeds standard sample customer & order data."""
        try:
            conn = sqlite3.connect(self.sqlite_db_path)
            cur = conn.cursor()
            cur.execute("DELETE FROM customers;")
            cur.execute("DELETE FROM orders;")
            cur.execute("DELETE FROM support_tickets;")
            cur.execute("DELETE FROM products_faq;")

            cur.executemany(
                "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?);",
                [
                    ("CUST-101", "Amara Perera", "amara.p@example.lk", "VIP Premium", "Active", 145000.0),
                    ("CUST-102", "Ruwan Fernando", "ruwan.f@example.lk", "Gold", "Active", 82000.0),
                    ("CUST-103", "Dilini Silva", "dilini.s@example.lk", "Standard", "Active", 23500.0),
                ]
            )
            cur.executemany(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?);",
                [
                    ("ORD-9021", "CUST-101", "Voice AI Router Enterprise Package", 45000.0, "Delivered", "2026-08-01"),
                    ("ORD-9022", "CUST-102", "Smart Customer Bot Add-on", 18500.0, "Processing", "2026-08-10"),
                    ("ORD-9023", "CUST-101", "Cloud Vector Storage Expansion", 12000.0, "Shipped", "2026-08-11"),
                ]
            )
            cur.executemany(
                "INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?);",
                [
                    ("TCK-5501", "Amara Perera", "API Integration", "Needs assistance setting up custom webhook for Voice RAG", "In Progress", "High"),
                    ("TCK-5502", "Ruwan Fernando", "Billing Inquiry", "Requesting VAT invoice for Order ORD-9022", "Resolved", "Medium"),
                ]
            )
            cur.executemany(
                "INSERT INTO products_faq VALUES (?, ?, ?, ?, ?);",
                [
                    ("FAQ-1", "Refund Policy", "What is the refund period for Voice RAG Bot subscriptions?", "Refunds are processed within 14 business days of submission upon approval by support.", "Billing"),
                    ("FAQ-2", "Supported Audio Formats", "Which audio input formats are accepted by the bot?", "The bot accepts WAV, MP3, M4A, WEBM, and OGG audio streams for real-time speech recognition.", "Technical"),
                ]
            )
            conn.commit()
            conn.close()
            return {"status": "success", "message": "Reseeded sample customer & order database tables successfully."}
        except Exception as e:
            logger.error(f"Reseed error: {e}")
            raise

    def reset_all_data(self) -> Dict[str, Any]:
        """Clears all customer datasets, orders, and custom uploaded tables."""
        try:
            conn = sqlite3.connect(self.sqlite_db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cur.fetchall() if not row[0].startswith("sqlite_")]
            for t in tables:
                cur.execute(f"DELETE FROM {t};")
            conn.commit()
            conn.close()
            return {"status": "success", "message": "Cleared all customer database records and uploaded datasets."}
        except Exception as e:
            logger.error(f"Reset error: {e}")
            raise

    def list_databases(self) -> List[Dict[str, Any]]:
        """Returns list of registered active database connections and summary."""
        result = []
        
        # 1. Primary PostgreSQL / In-Memory DB
        pg_connected = is_db_connected()
        result.append({
            "id": "primary_db",
            "name": "Primary Database (PostgreSQL + pgvector)" if pg_connected else "Primary Database (In-Memory Store)",
            "type": "postgresql" if pg_connected else "in_memory",
            "status": "connected",
            "is_builtin": True,
            "table_count": 4 if pg_connected else 4,
            "tables": ["documents", "document_chunks", "chat_history", "students"]
        })

        # 2. Registered SQLite / Postgres / Uploaded CSV databases
        for db_id, db_info in self.databases.items():
            schemas = self.get_database_schema(db_id)
            result.append({
                "id": db_id,
                "name": db_info["name"],
                "type": db_info["type"],
                "status": "connected",
                "is_builtin": db_info.get("is_builtin", False),
                "table_count": len(schemas),
                "tables": [s["table_name"] for s in schemas]
            })

        return result

    def get_database_schema(self, db_id: str) -> List[Dict[str, Any]]:
        """Extracts table schema (tables, columns, types) for a specific database ID."""
        schemas = []
        if db_id == "primary_db":
            # Primary PostgreSQL schema
            with get_db_connection() as conn:
                if conn:
                    try:
                        with conn.cursor() as cur:
                            cur.execute("""
                                SELECT table_name, column_name, data_type 
                                FROM information_schema.columns 
                                WHERE table_schema = 'public' 
                                ORDER BY table_name, ordinal_position;
                            """)
                            rows = cur.fetchall()
                            table_map: Dict[str, List[Dict[str, str]]] = {}
                            for r in rows:
                                table_map.setdefault(r[0], []).append({"column": r[1], "type": r[2]})
                            for t_name, cols in table_map.items():
                                schemas.append({"table_name": t_name, "columns": cols})
                    except Exception as e:
                        logger.error(f"Error fetching PG schema: {e}")
            if not schemas:
                # In-memory fallback
                schemas = [
                    {"table_name": "students", "columns": [{"column": "student_id", "type": "VARCHAR"}, {"column": "name", "type": "VARCHAR"}, {"column": "email", "type": "VARCHAR"}, {"column": "department", "type": "VARCHAR"}, {"column": "gpa", "type": "NUMERIC"}, {"column": "enrolled_year", "type": "INT"}, {"column": "status", "type": "VARCHAR"}]},
                    {"table_name": "documents", "columns": [{"column": "id", "type": "UUID"}, {"column": "title", "type": "VARCHAR"}, {"column": "file_type", "type": "VARCHAR"}]},
                ]
            return schemas

        db_info = self.databases.get(db_id)
        if not db_info:
            return []

        if db_info["type"] == "sqlite":
            try:
                conn = sqlite3.connect(db_info["uri_or_path"])
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                tables = [t[0] for t in cur.fetchall()]
                for t in tables:
                    cur.execute(f"PRAGMA table_info('{t}');")
                    cols = [{"column": col[1], "type": col[2] or "TEXT"} for col in cur.fetchall()]
                    schemas.append({"table_name": t, "columns": cols})
                conn.close()
            except Exception as e:
                logger.error(f"Error reading SQLite schema for {db_id}: {e}")
        elif db_info["type"] in ["postgresql", "postgres", "mysql"]:
            # External psycopg2 connection schema
            try:
                import psycopg2
                conn = psycopg2.connect(db_info["uri_or_path"], connect_timeout=3)
                cur = conn.cursor()
                cur.execute("""
                    SELECT table_name, column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name, ordinal_position;
                """)
                rows = cur.fetchall()
                table_map = {}
                for r in rows:
                    table_map.setdefault(r[0], []).append({"column": r[1], "type": r[2]})
                for t_name, cols in table_map.items():
                    schemas.append({"table_name": t_name, "columns": cols})
                conn.close()
            except Exception as e:
                logger.error(f"Error reading Postgres/MySQL schema for {db_id}: {e}")

        return schemas

    def get_all_schemas_summary(self) -> str:
        """Generates a clean text prompt representation of all active DB schemas + sample data rows for LLM Text-to-SQL synthesis."""
        all_dbs = self.list_databases()
        summary_lines = []
        for db in all_dbs:
            schemas = self.get_database_schema(db["id"])
            if not schemas:
                continue
            summary_lines.append(f"DATABASE: {db['name']} (id: {db['id']}, type: {db['type']})")
            for s in schemas:
                col_strs = [f"{c['column']} ({c['type']})" for c in s["columns"]]
                summary_lines.append(f"  - Table '{s['table_name']}': {', '.join(col_strs)}")
                
                # Fetch 2 sample data rows for value awareness
                try:
                    sample_res = self.execute_safe_sql(f"SELECT * FROM {s['table_name']} LIMIT 2;", db_id=db["id"])
                    if sample_res and sample_res.get("rows"):
                        sample_str = json.dumps(sample_res["rows"][:2])
                        summary_lines.append(f"    Sample Row Values: {sample_str}")
                except Exception:
                    pass
        return "\n".join(summary_lines)

    def register_connection(self, name: str, db_type: str, uri_or_path: str) -> Dict[str, Any]:
        """Registers a new external database connection (PostgreSQL, MySQL, or SQLite)."""
        db_id = f"db_{re.sub(r'[^a-zA-Z0-9]', '_', name.lower())}_{len(self.databases) + 1}"
        
        # Test connection validity
        if db_type == "sqlite":
            if not os.path.exists(uri_or_path):
                raise ValueError(f"SQLite file path does not exist: {uri_or_path}")
            conn = sqlite3.connect(uri_or_path)
            conn.close()
        elif db_type in ["postgresql", "postgres"]:
            import psycopg2
            conn = psycopg2.connect(uri_or_path, connect_timeout=3)
            conn.close()

        self.databases[db_id] = {
            "id": db_id,
            "name": name,
            "type": db_type,
            "uri_or_path": uri_or_path,
            "is_builtin": False,
        }
        return {"db_id": db_id, "name": name, "status": "connected"}

    def ingest_csv_as_table(self, table_name: str, csv_filename: str, csv_bytes: bytes) -> Dict[str, Any]:
        """Ingests a CSV or JSON file into the Customer SQLite database as a new queryable table."""
        clean_table_name = re.sub(r"[^a-zA-Z0-9_]", "_", table_name.lower().strip())
        if not clean_table_name or clean_table_name[0].isdigit():
            clean_table_name = f"table_{clean_table_name}"

        try:
            if csv_filename.endswith(".json"):
                df = pd.read_json(io.BytesIO(csv_bytes))
            else:
                df = pd.read_csv(io.BytesIO(csv_bytes))

            df.columns = [re.sub(r"[^a-zA-Z0-9_]", "_", str(col).lower().strip()) for col in df.columns]

            conn = sqlite3.connect(self.sqlite_db_path)
            df.to_sql(clean_table_name, conn, if_exists="replace", index=False)
            conn.close()

            logger.info(f"Successfully ingested CSV dataset into SQLite table '{clean_table_name}' with {len(df)} rows.")
            return {
                "tableName": clean_table_name,
                "rowCount": len(df),
                "columns": list(df.columns),
                "db_id": "customer_support_db"
            }
        except Exception as e:
            logger.error(f"Error ingesting CSV to SQLite table '{clean_table_name}': {e}")
            raise RuntimeError(f"Failed to parse CSV dataset: {e}")

    def execute_safe_sql(self, sql_query: str, db_id: Optional[str] = "customer_support_db") -> Dict[str, Any]:
        """Validates that SQL is read-only SELECT and executes against the target database."""
        clean_sql = sql_query.strip()
        # Security guard: Only allow read-only SELECT or WITH statements
        if not re.match(r"^(SELECT|WITH)\b", clean_sql, re.IGNORECASE):
            raise ValueError("Unauthorized SQL command. Only read-only SELECT queries are allowed.")
        if any(forbidden in clean_sql.upper() for forbidden in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"]):
            raise ValueError("Modifying SQL statements are strictly forbidden for AI query execution.")

        target_id = db_id or "customer_support_db"
        if target_id == "primary_db":
            with get_db_connection() as conn:
                if not conn:
                    return {"columns": [], "rows": [], "error": "Primary DB not connected."}
                try:
                    with conn.cursor() as cur:
                        cur.execute(clean_sql)
                        cols = [desc[0] for desc in cur.description] if cur.description else []
                        rows = cur.fetchall()
                        formatted_rows = [dict(zip(cols, row)) for row in rows]
                        return {"columns": cols, "rows": formatted_rows, "rowCount": len(formatted_rows), "query": clean_sql}
                except Exception as e:
                    return {"columns": [], "rows": [], "error": str(e), "query": clean_sql}

        db_info = self.databases.get(target_id)
        if not db_info:
            target_id = "customer_support_db"
            db_info = self.databases.get(target_id)

        if db_info and db_info["type"] == "sqlite":
            try:
                conn = sqlite3.connect(db_info["uri_or_path"])
                cur = conn.cursor()
                cur.execute(clean_sql)
                cols = [desc[0] for desc in cur.description] if cur.description else []
                rows = cur.fetchall()
                formatted_rows = [dict(zip(cols, row)) for row in rows]
                conn.close()
                return {"columns": cols, "rows": formatted_rows, "rowCount": len(formatted_rows), "query": clean_sql}
            except Exception as e:
                return {"columns": [], "rows": [], "error": str(e), "query": clean_sql}

        return {"columns": [], "rows": [], "error": "Database target not found.", "query": clean_sql}

    def remove_database(self, db_id: str) -> bool:
        """Removes a registered database connection."""
        if db_id in self.databases:
            if self.databases[db_id].get("is_builtin"):
                raise ValueError("Cannot remove built-in databases.")
            del self.databases[db_id]
            return True
        return False

# Global Database Manager Singleton
db_manager = DatabaseManager()


# --- BACKWARD COMPATIBLE STUDENT HELPER FUNCTIONS ---
def extract_student_id(query_str: str) -> Optional[str]:
    """Detects student ID patterns in user queries e.g. STU1042, student 1042."""
    if not query_str:
        return None
    clean = query_str.strip()
    match = re.search(r"\bSTU[-_]?(\d{3,6})\b", clean, re.IGNORECASE)
    if match:
        return f"STU{match.group(1)}"
    match = re.search(r"(?:student|id|stu|ශිෂ්‍ය|අංක)\s*[:#-]?\s*(\d{3,6})\b", clean, re.IGNORECASE)
    if match:
        return f"STU{match.group(1)}"
    match = re.search(r"\b(\d{3,6})\b", clean)
    if match:
        return f"STU{match.group(1)}"
    return None

def query_student_by_id_or_name(search_term: str) -> Optional[Dict[str, Any]]:
    """Queries PostgreSQL or InMemoryStore for a student by student_id or name."""
    if not search_term:
        return None
    clean_term = search_term.strip()
    student_id = extract_student_id(clean_term)

    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    if student_id:
                        cur.execute(
                            "SELECT student_id, name, email, department, gpa, enrolled_year, status FROM students WHERE LOWER(student_id) = LOWER(%s) OR LOWER(student_id) = LOWER(%s) OR LOWER(student_id) LIKE LOWER(%s);",
                            (student_id, clean_term, f"%{clean_term}%")
                        )
                        row = cur.fetchone()
                        if row:
                            return {
                                "student_id": row[0],
                                "name": row[1],
                                "email": row[2],
                                "department": row[3],
                                "gpa": float(row[4]) if row[4] is not None else None,
                                "enrolled_year": row[5],
                                "status": row[6],
                            }
                    cur.execute(
                        "SELECT student_id, name, email, department, gpa, enrolled_year, status FROM students WHERE LOWER(name) LIKE LOWER(%s);",
                        (f"%{clean_term}%",)
                    )
                    row = cur.fetchone()
                    if row:
                        return {
                            "student_id": row[0],
                            "name": row[1],
                            "email": row[2],
                            "department": row[3],
                            "gpa": float(row[4]) if row[4] is not None else None,
                            "enrolled_year": row[5],
                            "status": row[6],
                        }
            except Exception as e:
                logger.error(f"Error querying student from DB: {e}")
        else:
            students = in_memory_store.students
            if student_id:
                for s in students:
                    if s["student_id"].lower() == student_id.lower() or s["student_id"].lower() == clean_term.lower() or clean_term.lower() in s["student_id"].lower():
                        return s
            for s in students:
                if clean_term.lower() in s["name"].lower():
                    return s

    return None

def get_all_students() -> List[Dict[str, Any]]:
    """Returns all students from PostgreSQL or InMemoryStore."""
    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT student_id, name, email, department, gpa, enrolled_year, status FROM students ORDER BY student_id ASC;")
                    rows = cur.fetchall()
                    return [
                        {
                            "student_id": row[0],
                            "name": row[1],
                            "email": row[2],
                            "department": row[3],
                            "gpa": float(row[4]) if row[4] is not None else None,
                            "enrolled_year": row[5],
                            "status": row[6],
                        }
                        for row in rows
                    ]
            except Exception as e:
                logger.error(f"Error fetching students from DB: {e}")
                return []
        else:
            return in_memory_store.students

def upsert_student(student_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts or updates a student record in PostgreSQL or InMemoryStore."""
    student_id = student_data.get("student_id")
    if not student_id:
        raise ValueError("student_id is required.")

    name = student_data.get("name", "Unknown")
    email = student_data.get("email", "")
    department = student_data.get("department", "General")
    gpa = float(student_data.get("gpa", 0.0))
    enrolled_year = int(student_data.get("enrolled_year", 2024))
    status = student_data.get("status", "Active")

    record = {
        "student_id": student_id,
        "name": name,
        "email": email,
        "department": department,
        "gpa": gpa,
        "enrolled_year": enrolled_year,
        "status": status,
    }

    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
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
                        (student_id, name, email, department, gpa, enrolled_year, status)
                    )
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Error upserting student in DB: {e}")
                raise e
        else:
            existing = next((s for s in in_memory_store.students if s["student_id"].lower() == student_id.lower()), None)
            if existing:
                existing.update(record)
            else:
                in_memory_store.students.append(record)

    return record

