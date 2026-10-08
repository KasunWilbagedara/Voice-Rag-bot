"""
Customer Order Tracking Tool.

Searches customer orders by Order ID (e.g. ORD-9021 or ORD-1002) in the local database.
"""

import re
from typing import Dict, Any

from backend_with_tools import db_query_service
from backend_with_tools.tools.base import register_tool


@register_tool(
    name="track_customer_order",
    description="Tracks an order by Order ID (e.g. ORD-9021). Returns customer ID, product, amount, status, and order date.",
)
def track_customer_order(order_id: str) -> Dict[str, Any]:
    """Look up order details by order ID."""
    clean_id = order_id.upper().strip()
    match = re.search(r"\b(ORD-\d{3,8})\b", clean_id)
    target_id = match.group(1) if match else clean_id

    sql = f"SELECT * FROM orders WHERE UPPER(order_id) = '{target_id}' OR order_id LIKE '%{target_id}%' LIMIT 1;"
    res = db_query_service.db_manager.execute_safe_sql(sql, db_id="customer_support_db")
    if res.get("rows"):
        return {"order": res["rows"][0], "status": "found"}
    return {"order_id": target_id, "status": "not_found", "message": f"No order found with ID {target_id}"}
