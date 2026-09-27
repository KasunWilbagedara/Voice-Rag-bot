"""
services/db_query/executor.py — Safe SQL Executor
===================================================
Exposes ``execute_dynamic_sql()`` — the primary public function used by the
databases router and tool registry.

Security model:
  - Only ``SELECT`` or ``WITH`` statements are accepted.
  - ``DROP``, ``DELETE``, ``UPDATE``, ``INSERT``, ``ALTER``, ``TRUNCATE``,
    ``CREATE`` are explicitly blocked.
  - Results are truncated to ``MAX_ROWS`` rows to prevent memory exhaustion.
"""

import re
import logging
from typing import Any, Dict, List, Optional

from backend.services.db_query.manager import db_manager

logger = logging.getLogger("voicerag.db_query.executor")

MAX_ROWS = 500  # hard cap to prevent runaway memory usage


def execute_dynamic_sql(
    sql_query: str,
    db_id: Optional[str] = "customer_support_db",
) -> Dict[str, Any]:
    """
    Validates and executes a read-only SQL query against the specified database.

    Delegates to ``db_manager.execute_safe_sql()`` after performing an
    additional result-row truncation guard.

    Args:
        sql_query: A read-only ``SELECT`` or ``WITH`` statement.
        db_id:     Target database identifier (default ``"customer_support_db"``).

    Returns:
        Dict with keys ``columns``, ``rows``, ``rowCount``, ``query``;
        or ``columns``, ``rows``, ``error``, ``query`` on failure.

    Raises:
        ValueError: If ``sql_query`` contains forbidden DML/DDL keywords.
    """
    result = db_manager.execute_safe_sql(sql_query=sql_query, db_id=db_id)

    # Truncate oversized result sets
    if result.get("rows") and len(result["rows"]) > MAX_ROWS:
        logger.warning(
            "SQL result truncated from %d to %d rows for query: %.80s",
            len(result["rows"]),
            MAX_ROWS,
            sql_query,
        )
        result["rows"] = result["rows"][:MAX_ROWS]
        result["rowCount"] = MAX_ROWS
        result["truncated"] = True

    return result
