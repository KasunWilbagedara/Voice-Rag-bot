"""
services/db_query/students.py — Student Record Helpers
========================================================
Provides functions for reading and writing student records from PostgreSQL
(primary) or the in-memory fallback store:
  - extract_student_id()         — parse STU-ID from a query string
  - query_student_by_id_or_name() — look up one student by ID or name
  - get_all_students()            — return all students
  - upsert_student()              — insert or update a student record
"""

import re
import logging
from typing import Any, Dict, List, Optional

from backend.db import get_db_connection, in_memory_store

logger = logging.getLogger("voicerag.db_query.students")


def extract_student_id(query_str: str) -> Optional[str]:
    """
    Detects student ID patterns in a query string.

    Handles: ``STU1042``, ``STU-1042``, ``student 1042``, bare ``1042``.

    Args:
        query_str: Raw user query or search term.

    Returns:
        Normalised student ID string (e.g. ``"STU1042"``), or ``None``.
    """
    if not query_str:
        return None
    clean = query_str.strip()

    match = re.search(r"\bSTU[-_]?(\d{3,6})\b", clean, re.IGNORECASE)
    if match:
        return f"STU{match.group(1)}"

    match = re.search(
        r"(?:student|id|stu|ශිෂ්‍ය|අංක)\s*[:#-]?\s*(\d{3,6})\b",
        clean,
        re.IGNORECASE,
    )
    if match:
        return f"STU{match.group(1)}"

    match = re.search(r"\b(\d{3,6})\b", clean)
    if match:
        return f"STU{match.group(1)}"

    return None


def query_student_by_id_or_name(search_term: str) -> Optional[Dict[str, Any]]:
    """
    Queries PostgreSQL or InMemoryStore for a student by ID or name.

    Args:
        search_term: Student ID (``STU1042``) or partial name.

    Returns:
        Student record dict, or ``None`` if not found.
    """
    if not search_term:
        return None
    clean_term = search_term.strip()
    student_id = extract_student_id(clean_term)

    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    if student_id:
                        cur.execute(
                            "SELECT student_id, name, email, department, gpa, enrolled_year, status "
                            "FROM students "
                            "WHERE LOWER(student_id) = LOWER(%s) "
                            "   OR LOWER(student_id) = LOWER(%s) "
                            "   OR LOWER(student_id) LIKE LOWER(%s);",
                            (student_id, clean_term, f"%{clean_term}%"),
                        )
                        row = cur.fetchone()
                        if row:
                            return _row_to_dict(row)
                    cur.execute(
                        "SELECT student_id, name, email, department, gpa, enrolled_year, status "
                        "FROM students WHERE LOWER(name) LIKE LOWER(%s);",
                        (f"%{clean_term}%",),
                    )
                    row = cur.fetchone()
                    if row:
                        return _row_to_dict(row)
            except Exception as e:
                logger.error(f"Error querying student from DB: {e}")
        else:
            students = in_memory_store.students
            if student_id:
                for s in students:
                    sid = s["student_id"].lower()
                    if sid == student_id.lower() or sid == clean_term.lower() or clean_term.lower() in sid:
                        return s
            for s in students:
                if clean_term.lower() in s["name"].lower():
                    return s

    return None


def get_all_students() -> List[Dict[str, Any]]:
    """
    Returns all students from PostgreSQL or InMemoryStore.

    Returns:
        List of student record dicts ordered by ``student_id``.
    """
    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT student_id, name, email, department, gpa, enrolled_year, status "
                        "FROM students ORDER BY student_id ASC;"
                    )
                    return [_row_to_dict(row) for row in cur.fetchall()]
            except Exception as e:
                logger.error(f"Error fetching students from DB: {e}")
                return []
        else:
            return in_memory_store.students


def upsert_student(student_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts or updates a student record in PostgreSQL or InMemoryStore.

    Args:
        student_data: Dict with keys ``student_id``, ``name``, ``email``,
                      ``department``, ``gpa``, ``enrolled_year``, ``status``.

    Returns:
        The normalised student record dict.

    Raises:
        ValueError: If ``student_id`` is missing.
    """
    student_id = student_data.get("student_id")
    if not student_id:
        raise ValueError("student_id is required.")

    record: Dict[str, Any] = {
        "student_id": student_id,
        "name": student_data.get("name", "Unknown"),
        "email": student_data.get("email", ""),
        "department": student_data.get("department", "General"),
        "gpa": float(student_data.get("gpa", 0.0)),
        "enrolled_year": int(student_data.get("enrolled_year", 2024)),
        "status": student_data.get("status", "Active"),
    }

    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO students
                            (student_id, name, email, department, gpa, enrolled_year, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (student_id) DO UPDATE SET
                            name          = EXCLUDED.name,
                            email         = EXCLUDED.email,
                            department    = EXCLUDED.department,
                            gpa           = EXCLUDED.gpa,
                            enrolled_year = EXCLUDED.enrolled_year,
                            status        = EXCLUDED.status;
                        """,
                        (
                            record["student_id"], record["name"], record["email"],
                            record["department"], record["gpa"],
                            record["enrolled_year"], record["status"],
                        ),
                    )
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Error upserting student in DB: {e}")
                raise
        else:
            existing = next(
                (s for s in in_memory_store.students if s["student_id"].lower() == student_id.lower()),
                None,
            )
            if existing:
                existing.update(record)
            else:
                in_memory_store.students.append(record)

    return record


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "student_id":    row[0],
        "name":          row[1],
        "email":         row[2],
        "department":    row[3],
        "gpa":           float(row[4]) if row[4] is not None else None,
        "enrolled_year": row[5],
        "status":        row[6],
    }
