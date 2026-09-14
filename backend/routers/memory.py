import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import (
    save_or_update_memory,
    get_user_memories,
    delete_memory,
    clear_all_memories,
    get_saved_chat_history,
    clear_saved_chat_history,
)

logger = logging.getLogger("voicerag.memory_router")

router = APIRouter(tags=["Memory & History"])


class MemoryCreateRequest(BaseModel):
    key: str
    value: str
    category: Optional[str] = "note"
    sessionId: Optional[str] = "default_user"


# ---------------- MEMORY ENDPOINTS ----------------

@router.get("/api/memory")
def list_memories(session_id: str = Query("default_user", alias="sessionId")):
    """Retrieves all active remembered facts for a session."""
    try:
        memories = get_user_memories(session_id)
        return {
            "success": True,
            "sessionId": session_id,
            "memories": memories,
            "count": len(memories),
        }
    except Exception as e:
        logger.error(f"Error fetching memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/memory")
def add_or_update_memory(req: MemoryCreateRequest):
    """Saves or updates a remembered fact."""
    if not req.key.strip() or not req.value.strip():
        raise HTTPException(status_code=400, detail="Both 'key' and 'value' are required.")

    session_id = req.sessionId or "default_user"
    category = req.category or "note"

    try:
        success = save_or_update_memory(session_id, req.key.strip(), req.value.strip(), category.strip())
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save memory fact.")

        updated_memories = get_user_memories(session_id)
        return {
            "success": True,
            "message": "Memory saved successfully.",
            "memories": updated_memories,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/memory/{memory_id}")
def remove_memory(memory_id: str):
    """Deletes a specific remembered fact by ID."""
    try:
        success = delete_memory(memory_id)
        return {
            "success": success,
            "deletedId": memory_id,
        }
    except Exception as e:
        logger.error(f"Error deleting memory {memory_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/memory")
def clear_memories(session_id: str = Query("default_user", alias="sessionId")):
    """Clears all stored memories for the session."""
    try:
        success = clear_all_memories(session_id)
        return {
            "success": success,
            "message": f"All memories for session '{session_id}' cleared.",
        }
    except Exception as e:
        logger.error(f"Error clearing memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- CONVERSATION HISTORY ENDPOINTS ----------------

@router.get("/api/history")
def list_history(limit: int = Query(30, ge=1, le=100)):
    """Retrieves saved conversation history across sessions."""
    try:
        history = get_saved_chat_history(limit=limit)
        return {
            "success": True,
            "history": history,
            "count": len(history),
        }
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/history")
def clear_history():
    """Clears all persistent conversation history."""
    try:
        success = clear_saved_chat_history()
        return {
            "success": success,
            "message": "Chat history cleared successfully.",
        }
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
