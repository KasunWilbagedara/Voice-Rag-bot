"""
Database Inspection and Schema Discovery Tools.

Provides:
- list_databases: Discovers connected databases, tables, and record counts.
- get_database_schema: Returns table schemas, column names, and data types.
"""

from typing import List, Dict, Any

from backend_with_tools import db_query_service
from backend_with_tools.tools.base import register_tool


@register_tool(
    name="list_databases",
    description="Returns all active database connections, table counts, and registered dataset tables.",
)
def list_databases() -> List[Dict[str, Any]]:
    """Lists all connected databases and their table lists."""
    return db_query_service.db_manager.list_databases()


@register_tool(
    name="get_database_schema",
    description="Returns the column names and data types for all tables in a specific database ID.",
)
def get_database_schema(db_id: str = "customer_support_db") -> List[Dict[str, Any]]:
    """Inspects the schema of a database."""
    return db_query_service.db_manager.get_database_schema(db_id)
