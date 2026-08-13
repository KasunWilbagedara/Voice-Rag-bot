import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.rag_service import (
    delete_chat_session,
    ensure_chat_session,
    list_chat_sessions,
    update_chat_session_title,
)

router = APIRouter(prefix="/api/chat/sessions", tags=["Chat Sessions"])
logger = logging.getLogger("voicerag.chat_sessions_router")


class ChatSessionRequest(BaseModel):
    sessionId: Optional[str] = None
    userId: Optional[str] = "local-user"
    title: Optional[str] = "New Chat"


class ChatSessionTitleRequest(BaseModel):
    userId: Optional[str] = "local-user"
    title: str


@router.get("")
def get_chat_sessions(userId: str = Query("local-user")):
    try:
        return {"sessions": list_chat_sessions(user_id=userId or "local-user")}
    except Exception as e:
        logger.error(f"Chat sessions listing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_chat_session(req: ChatSessionRequest):
    try:
        session = ensure_chat_session(
            session_id=req.sessionId,
            user_id=req.userId or "local-user",
            title=req.title or "New Chat",
        )
        return {"session": session}
    except Exception as e:
        logger.error(f"Chat session creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{session_id}")
def rename_chat_session(session_id: str, req: ChatSessionTitleRequest):
    try:
        session = update_chat_session_title(
            session_id=session_id,
            title=req.title,
            user_id=req.userId or "local-user",
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found.")
        return {"session": session}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat session rename error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
def remove_chat_session(session_id: str, userId: str = Query("local-user")):
    try:
        deleted = delete_chat_session(session_id=session_id, user_id=userId or "local-user")
        if not deleted:
            raise HTTPException(status_code=404, detail="Chat session not found.")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat session delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
