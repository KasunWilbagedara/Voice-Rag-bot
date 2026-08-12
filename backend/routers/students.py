import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db_query_service import (
    get_all_students,
    query_student_by_id_or_name,
    upsert_student,
)
from backend.db import seed_initial_students

router = APIRouter(prefix="/api/students", tags=["Students Database"])
logger = logging.getLogger("voicerag.students_router")

class StudentModel(BaseModel):
    student_id: str
    name: str
    email: Optional[str] = ""
    department: Optional[str] = "General"
    gpa: Optional[float] = 0.0
    enrolled_year: Optional[int] = 2024
    status: Optional[str] = "Active"

@router.get("", response_model=List[Dict[str, Any]])
def list_students():
    """Lists all student records in the database."""
    try:
        return get_all_students()
    except Exception as e:
        logger.error(f"Error listing students: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{student_id}")
def get_student(student_id: str):
    """Retrieves details for a specific student ID or name."""
    student = query_student_by_id_or_name(student_id)
    if not student:
        raise HTTPException(status_code=404, detail=f"Student ID '{student_id}' not found.")
    return student

@router.post("")
def add_or_update_student(student: StudentModel):
    """Adds a new student or updates an existing student record."""
    try:
        updated = upsert_student(student.model_dump())
        return {"status": "success", "student": updated}
    except Exception as e:
        logger.error(f"Error saving student record: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/seed")
def seed_students():
    """Re-seeds initial sample student database records."""
    try:
        seed_initial_students()
        return {"status": "success", "message": "Sample student records seeded successfully.", "students": get_all_students()}
    except Exception as e:
        logger.error(f"Error seeding students: {e}")
        raise HTTPException(status_code=500, detail=str(e))
