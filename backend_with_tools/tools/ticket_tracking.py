"""
Customer Support Ticket Tracking Tool.

Searches support tickets by Ticket ID (e.g. TCK-5501 or TCK-1001) in the local database.
"""

import re
from typing import Dict, Any

from backend_with_tools import db_query_service
from backend_with_tools.tools.base import register_tool


@register_tool(
    name="track_support_ticket",
    description="Tracks a customer support ticket by Ticket ID (e.g. TCK-5501). Returns customer name, issue category, description, and status.",
)
def track_support_ticket(ticket_id: str) -> Dict[str, Any]:
    """Look up ticket details by ticket ID."""
    clean_id = ticket_id.upper().strip()
    match = re.search(r"\b(TCK-\d{3,8})\b", clean_id)
    target_id = match.group(1) if match else clean_id

    sql = f"SELECT * FROM support_tickets WHERE UPPER(ticket_id) = '{target_id}' OR ticket_id LIKE '%{target_id}%' LIMIT 1;"
    res = db_query_service.db_manager.execute_safe_sql(sql, db_id="customer_support_db")
    if res.get("rows"):
        return {"ticket": res["rows"][0], "status": "found"}
    return {"ticket_id": target_id, "status": "not_found", "message": f"No support ticket found with ID {target_id}"}
