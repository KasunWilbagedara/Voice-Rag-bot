"""
Student Academic Record Lookup Tool.

Finds student academic profile, GPA, enrollment year, and status by student ID
(e.g. STU1042) or student name.
"""

from typing import Dict, Any, Optional

from backend_with_tools import db_query_service
from backend_with_tools.tools.base import register_tool


@register_tool(
    name="lookup_student",
    description="Finds student academic profile, GPA, enrollment year, and status by student ID (e.g. STU1042) or student name.",
)
def lookup_student(search_term: str) -> Optional[Dict[str, Any]]:
    """Lookup a student record from PostgreSQL or local student database."""
    return db_query_service.query_student_by_id_or_name(search_term)
