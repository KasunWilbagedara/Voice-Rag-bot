import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth import current_user_id
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

# When logged in, the session is always the user's own id — the sessionId
# parameter is only used when AUTH_REQUIRED is turned off.


class MemoryCreateRequest(BaseModel):
    key: str
    value: str
    category: Optional[str] = "note"
    sessionId: Optional[str] = "default_user"


# ---------------- MEMORY ENDPOINTS ----------------

@router.get("/api/memory")
def list_memories(
    session_param: str = Query("default_user", alias="sessionId"),
    user_id: Optional[str] = Depends(current_user_id),
):
    """Retrieves all remembered facts for the user."""
    session_id = user_id or session_param
    try:
        memories = get_user_memories(session_id)
        return {"success": True, "sessionId": session_id, "memories": memories, "count": len(memories)}
    except Exception as e:
        logger.error(f"Error fetching memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/memory")
def add_or_update_memory(req: MemoryCreateRequest, user_id: Optional[str] = Depends(current_user_id)):
    """Saves or updates a remembered fact."""
    if not req.key.strip() or not req.value.strip():
        raise HTTPException(status_code=400, detail="Both 'key' and 'value' are required.")

    session_id = user_id or req.sessionId or "default_user"
    try:
        saved = save_or_update_memory(session_id, req.key.strip(), req.value.strip(), (req.category or "note").strip())
        if not saved:
            raise HTTPException(status_code=500, detail="Failed to save memory fact.")
        return {"success": True, "message": "Memory saved successfully.", "memories": get_user_memories(session_id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/memory/{memory_id}")
def remove_memory(memory_id: str, user_id: Optional[str] = Depends(current_user_id)):
    """Deletes one remembered fact (only the user's own when logged in)."""
    try:
        return {"success": delete_memory(memory_id, session_id=user_id), "deletedId": memory_id}
    except Exception as e:
        logger.error(f"Error deleting memory {memory_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/memory")
def clear_memories(
    session_param: str = Query("default_user", alias="sessionId"),
    user_id: Optional[str] = Depends(current_user_id),
):
    """Clears all stored memories for the user."""
    session_id = user_id or session_param
    try:
        return {"success": clear_all_memories(session_id), "message": "All memories cleared."}
    except Exception as e:
        logger.error(f"Error clearing memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- CONVERSATION HISTORY ENDPOINTS ----------------

@router.get("/api/history")
def list_history(
    limit: int = Query(30, ge=1, le=100),
    session_param: Optional[str] = Query(None, alias="sessionId"),
    user_id: Optional[str] = Depends(current_user_id),
):
    """Retrieves the user's saved conversation history (newest first)."""
    try:
        history = get_saved_chat_history(limit=limit, session_id=user_id or session_param)
        return {"success": True, "history": history, "count": len(history)}
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/history")
def clear_history(
    session_param: Optional[str] = Query(None, alias="sessionId"),
    user_id: Optional[str] = Depends(current_user_id),
):
    """Clears the user's conversation history."""
    try:
        success = clear_saved_chat_history(user_id or session_param)
        return {"success": success, "message": "Chat history cleared successfully."}
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
