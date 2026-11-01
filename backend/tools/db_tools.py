"""
tools/db_tools.py — Database, Student & Memory Tools
======================================================
Registers database-backed tools into the central TOOL_REGISTRY:
  - track_customer_order   — look up order by ORD-XXXX ID
  - track_support_ticket   — look up ticket by TCK-XXXX ID
  - lookup_student         — search student by ID or name
  - execute_sql            — safe read-only SQL against any connected DB
  - list_databases         — list registered database connections
  - get_database_schema    — inspect table columns for a specific DB
  - get_session_memories   — fetch persistent user memory for a session
  - save_session_memory    — store a fact/entity into persistent memory
  - search_knowledge_base  — cross-lingual hybrid RAG vector + BM25 search
"""

import logging
import re
from typing import Any, Dict, List, Optional

from backend.tools.registry import register_tool
from backend.services.db_query import db_manager, query_student_by_id_or_name
from backend.db import get_user_memories, save_or_update_memory

logger = logging.getLogger("voicerag.tools.db")


# ---------------------------------------------------------------------------
# 1. Customer Order Tracking
# ---------------------------------------------------------------------------

@register_tool(
    name="track_customer_order",
    description=(
        "Tracks an order by Order ID (e.g. ORD-9021). "
        "Returns customer ID, product, amount, status, and order date."
    ),
)
def track_customer_order(order_id: str) -> Dict[str, Any]:
    """Look up order details by order ID."""
    clean_id = order_id.upper().strip()
    match = re.search(r"\b(ORD-\d{3,8})\b", clean_id)
    target_id = match.group(1) if match else clean_id

    sql = f"SELECT * FROM orders WHERE UPPER(order_id) = '{target_id}' OR order_id LIKE '%{target_id}%' LIMIT 1;"
    res = db_manager.execute_safe_sql(sql, db_id="customer_support_db")
    if res.get("rows"):
        return {"order": res["rows"][0], "status": "found"}
    return {"order_id": target_id, "status": "not_found", "message": f"No order found with ID {target_id}"}


# ---------------------------------------------------------------------------
# 2. Support Ticket Tracking
# ---------------------------------------------------------------------------

@register_tool(
    name="track_support_ticket",
    description=(
        "Tracks a customer support ticket by Ticket ID (e.g. TCK-5501). "
        "Returns customer name, issue category, description, and status."
    ),
)
def track_support_ticket(ticket_id: str) -> Dict[str, Any]:
    """Look up ticket details by ticket ID."""
    clean_id = ticket_id.upper().strip()
    match = re.search(r"\b(TCK-\d{3,8})\b", clean_id)
    target_id = match.group(1) if match else clean_id

    sql = f"SELECT * FROM support_tickets WHERE UPPER(ticket_id) = '{target_id}' OR ticket_id LIKE '%{target_id}%' LIMIT 1;"
    res = db_manager.execute_safe_sql(sql, db_id="customer_support_db")
    if res.get("rows"):
        return {"ticket": res["rows"][0], "status": "found"}
    return {"ticket_id": target_id, "status": "not_found", "message": f"No support ticket found with ID {target_id}"}


# ---------------------------------------------------------------------------
# 3. Student Lookup
# ---------------------------------------------------------------------------

@register_tool(
    name="lookup_student",
    description=(
        "Finds student academic profile, GPA, enrollment year, and status "
        "by student ID (e.g. STU1042) or student name."
    ),
)
def lookup_student(search_term: str) -> Optional[Dict[str, Any]]:
    """Lookup a student record from PostgreSQL or in-memory student database."""
    return query_student_by_id_or_name(search_term)


# ---------------------------------------------------------------------------
# 4. Safe SQL Execution
# ---------------------------------------------------------------------------

@register_tool(
    name="execute_sql",
    description=(
        "Executes a safe read-only SQL SELECT query against a connected "
        "database (customer_support_db, primary_db)."
    ),
)
def execute_sql(sql_query: str, db_id: Optional[str] = "customer_support_db") -> Dict[str, Any]:
    """Runs a read-only SQL query against the target database."""
    return db_manager.execute_safe_sql(sql_query=sql_query, db_id=db_id)


# ---------------------------------------------------------------------------
# 5. List Databases
# ---------------------------------------------------------------------------

@register_tool(
    name="list_databases",
    description="Returns all active database connections, table counts, and registered dataset tables.",
)
def list_databases() -> List[Dict[str, Any]]:
    """Lists all connected databases and their table lists."""
    return db_manager.list_databases()


# ---------------------------------------------------------------------------
# 6. Get Database Schema
# ---------------------------------------------------------------------------

@register_tool(
    name="get_database_schema",
    description="Returns the column names and data types for all tables in a specific database ID.",
)
def get_database_schema(db_id: str = "customer_support_db") -> List[Dict[str, Any]]:
    """Inspects the schema of a database."""
    return db_manager.get_database_schema(db_id)


# ---------------------------------------------------------------------------
# 7. Session Memory Read
# ---------------------------------------------------------------------------

@register_tool(
    name="get_session_memories",
    description=(
        "Retrieves all persistent remembered facts, identities, and entities "
        "stored for a user session."
    ),
)
def get_session_memories(session_id: str = "default_user") -> List[Dict[str, Any]]:
    """Fetches user memories for the given session ID."""
    return get_user_memories(session_id)


# ---------------------------------------------------------------------------
# 8. Session Memory Write
# ---------------------------------------------------------------------------

@register_tool(
    name="save_session_memory",
    description=(
        "Saves or updates a persistent user fact, entity, or preference "
        "(e.g., user_name, last_tracked_order)."
    ),
)
def save_session_memory(
    session_id: str, key: str, value: str, category: str = "general"
) -> bool:
    """Stores a fact into persistent memory."""
    try:
        save_or_update_memory(session_id=session_id, key=key, value=value, category=category)
        return True
    except Exception as e:
        logger.warning(f"Failed to save session memory: {e}")
        return False


# ---------------------------------------------------------------------------
# 9. RAG Knowledge Base Search
# ---------------------------------------------------------------------------

@register_tool(
    name="search_knowledge_base",
    description=(
        "Performs cross-lingual hybrid (Dense Vector + BM25 Lexical) search "
        "over ingested document chunks."
    ),
)
def search_knowledge_base(
    query_text: str,
    top_k: int = 8,
    custom_api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Searches vector & keyword database using query text."""
    from backend.rag import get_text_embedding, search_similar_chunks
    query_embedding = get_text_embedding(query_text, custom_api_key=custom_api_key)
    return search_similar_chunks(
        query_embedding=query_embedding,
        top_k=top_k,
        query_text=query_text,
        custom_api_key=custom_api_key,
    )
