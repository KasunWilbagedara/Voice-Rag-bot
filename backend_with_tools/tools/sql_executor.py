"""
Safe Read-Only SQL Executor Tool.

Executes read-only SQL queries against connected databases with AST/regex SQL injection protection.
"""

from typing import Dict, Any, Optional

from backend_with_tools import db_query_service
from backend_with_tools.tools.base import register_tool


@register_tool(
    name="execute_sql",
    description="Executes a safe read-only SQL SELECT query against a connected database (customer_support_db, primary_db).",
)
def execute_sql(sql_query: str, db_id: Optional[str] = "customer_support_db") -> Dict[str, Any]:
    """Runs a read-only SQL query against the target database."""
    return db_query_service.db_manager.execute_safe_sql(sql_query=sql_query, db_id=db_id)
