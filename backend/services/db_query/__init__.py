"""
backend/services/db_query/__init__.py — DB Query Package Public API
====================================================================
Single authoritative source for the db_query surface.
All symbols are implemented in the sub-modules below — no imports from the
legacy ``db_query_service.py`` monolith.

Sub-modules
-----------
manager      — DatabaseManager class & db_manager singleton
executor     — execute_dynamic_sql()
csv_importer — import_csv_to_sqlite()
students     — extract_student_id, query_student_by_id_or_name,
               get_all_students, upsert_student
"""

from backend.services.db_query.manager import DatabaseManager, db_manager
from backend.services.db_query.executor import execute_dynamic_sql
from backend.services.db_query.csv_importer import import_csv_to_sqlite
from backend.services.db_query.students import (
    extract_student_id,
    query_student_by_id_or_name,
    get_all_students,
    upsert_student,
)


def get_all_database_schemas() -> str:
    """
    Returns a plain-text prompt representation of all active DB schemas +
    sample data rows — suitable for LLM Text-to-SQL synthesis.
    """
    return db_manager.get_all_schemas_summary()


__all__ = [
    "DatabaseManager",
    "db_manager",
    "execute_dynamic_sql",
    "import_csv_to_sqlite",
    "get_all_database_schemas",
    "extract_student_id",
    "query_student_by_id_or_name",
    "get_all_students",
    "upsert_student",
]
