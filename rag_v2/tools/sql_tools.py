"""
rag_v2/tools/sql_tools.py
--------------------------
Read-only SQL execution tools for the RAG v2 database.

Tools
-----
- execute_sql        – Run a validated SELECT query and return rows as dicts.
- list_rag_documents – List all documents in the rag_v2_documents table.
"""

import logging
import re
from typing import Any, Dict, List

import psycopg2.extras

from rag_v2.tools.registry import register_tool
from rag_v2.storage.db import get_db_connection

logger = logging.getLogger("rag_v2.tools.sql_tools")

# ── Forbidden DML / DDL keywords (case-insensitive) ──────────────────────────
_FORBIDDEN_PATTERN = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|TRUNCATE|ALTER|CREATE|REPLACE|MERGE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

_LIMIT_PATTERN = re.compile(r"\bLIMIT\s+\d+", re.IGNORECASE)
_DEFAULT_LIMIT = 50


def _validate_and_sanitise(sql: str) -> str:
    """Ensure *sql* is a safe read-only SELECT statement.

    - Strips leading/trailing whitespace and trailing semicolons.
    - Raises :class:`ValueError` if any forbidden keyword is detected.
    - Appends ``LIMIT {_DEFAULT_LIMIT}`` when the query has no LIMIT clause.
    """
    clean = sql.strip().rstrip(";").strip()

    # Must start with SELECT (allow optional WITH for CTEs)
    if not re.match(r"^\s*(WITH\b|SELECT\b)", clean, re.IGNORECASE):
        raise ValueError(
            "Only SELECT statements (or CTEs starting with WITH … SELECT) are permitted."
        )

    # Block dangerous keywords
    match = _FORBIDDEN_PATTERN.search(clean)
    if match:
        raise ValueError(
            f"Forbidden keyword '{match.group()}' detected in SQL query. "
            "Only read-only SELECT queries are allowed."
        )

    # Inject LIMIT if absent to protect against unbounded scans
    if not _LIMIT_PATTERN.search(clean):
        clean = f"{clean} LIMIT {_DEFAULT_LIMIT}"

    return clean


# ─────────────────────────────────────────────────────────────────────────────
# Tool: execute_sql
# ─────────────────────────────────────────────────────────────────────────────

@register_tool(
    name="execute_sql",
    description=(
        "Execute a safe, read-only SQL SELECT query against the RAG v2 PostgreSQL "
        "database and return the results as a list of row dictionaries. "
        "Only SELECT statements are permitted; DDL and DML are blocked. "
        "A LIMIT 50 is automatically applied if not specified."
    ),
    parameters={
        "sql_query": {
            "type": "string",
            "description": (
                "The SQL SELECT statement to execute. "
                "Example: \"SELECT id, title FROM rag_v2_documents LIMIT 10\""
            ),
        }
    },
)
def execute_sql(sql_query: str) -> List[Dict[str, Any]]:
    """Validate and execute a read-only SQL query, returning rows as dicts."""
    try:
        safe_sql = _validate_and_sanitise(sql_query)
        logger.info("execute_sql: %s", safe_sql)

        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(safe_sql)
                rows = cur.fetchall()
        finally:
            conn.close()

        result = [dict(row) for row in rows]
        logger.info("execute_sql returned %d rows.", len(result))
        return result

    except ValueError as exc:
        logger.warning("execute_sql validation error: %s", exc)
        return [{"error": str(exc)}]
    except Exception as exc:
        logger.error("execute_sql unexpected error: %s", exc)
        return [{"error": f"Database error: {exc}"}]


# ─────────────────────────────────────────────────────────────────────────────
# Tool: list_rag_documents
# ─────────────────────────────────────────────────────────────────────────────

@register_tool(
    name="list_rag_documents",
    description=(
        "List all documents currently indexed in the RAG v2 knowledge base. "
        "Returns document metadata including ID, title, file type, chunk count, "
        "and ingestion timestamp, ordered by most recently added first."
    ),
    parameters={},
)
def list_rag_documents() -> List[Dict[str, Any]]:
    """Return metadata for every document in ``rag_v2_documents``."""
    try:
        sql = (
            "SELECT id, title, file_type, source_url, chunk_count, created_at "
            "FROM rag_v2_documents "
            "ORDER BY created_at DESC "
            f"LIMIT {_DEFAULT_LIMIT}"
        )
        logger.info("list_rag_documents: executing query.")

        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()
        finally:
            conn.close()

        result = [dict(row) for row in rows]
        logger.info("list_rag_documents returned %d documents.", len(result))
        return result

    except Exception as exc:
        logger.error("list_rag_documents error: %s", exc)
        return [{"error": f"Database error: {exc}"}]
