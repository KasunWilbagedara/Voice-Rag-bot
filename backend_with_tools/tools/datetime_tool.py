"""
Current Date and Time Tool.

Provides real-time timestamp, readable day/month/year, and timezone awareness.
"""

from datetime import datetime
from typing import Dict, Any

from backend_with_tools.tools.base import register_tool


@register_tool(
    name="get_current_datetime",
    description="Returns current date, local time, day of the week, and timezone information (defaults to Sri Lanka / Asia/Colombo).",
)
def get_current_datetime(timezone_str: str = "Asia/Colombo") -> Dict[str, Any]:
    """Returns exact current date and time."""
    now = datetime.now()
    return {
        "datetime_iso": now.isoformat(),
        "readable_date": now.strftime("%A, %B %d, %Y"),
        "readable_time": now.strftime("%I:%M:%S %p"),
        "day_of_week": now.strftime("%A"),
        "year": now.year,
        "month": now.strftime("%B"),
        "day": now.day,
        "timezone": timezone_str,
        "status": "success",
    }
