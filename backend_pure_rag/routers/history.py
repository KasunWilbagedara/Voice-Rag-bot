import logging
from fastapi import APIRouter, HTTPException, Query
from backend_pure_rag.db import get_saved_chat_history, clear_saved_chat_history

router = APIRouter(prefix="/api/history", tags=["History (Pure RAG)"])
logger = logging.getLogger("pure_rag.history")


@router.get("")
def get_chat_history(limit: int = Query(30, ge=1, le=100)):
    try:
        history = get_saved_chat_history(limit)
        return {
            "success": True,
            "count": len(history),
            "history": history,
            "backendMode": "pure_rag",
        }
    except Exception as e:
        logger.error(f"Error fetching pure RAG history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
def delete_chat_history():
    try:
        cleared = clear_saved_chat_history()
        return {
            "success": cleared,
            "message": "Pure RAG conversation history cleared.",
        }
    except Exception as e:
        logger.error(f"Error clearing pure RAG history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
