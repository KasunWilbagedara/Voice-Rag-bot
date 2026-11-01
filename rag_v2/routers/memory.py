"""
Conversation memory router for RAG v2.

Exposes:
  GET    /api/v2/memory/{session_id}  — retrieve conversation history for a session
  DELETE /api/v2/memory/{session_id}  — clear conversation history for a session
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from rag_v2.storage.memory import clear_history, get_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["Memory"])


@router.get(
    "/memory/{session_id}",
    summary="Get conversation history for a session",
)
def get_session_history(session_id: str) -> JSONResponse:
    """
    Returns up to 50 messages for the given *session_id*, ordered from
    oldest to newest.  Each entry contains a ``role`` (``user`` or
    ``assistant``) and the message ``content``.
    """
    try:
        history = get_history(session_id, limit=50)
    except Exception as exc:
        logger.exception(
            "Failed to retrieve history for session '%s': %s", session_id, exc
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversation history: {exc}",
        ) from exc

    # Normalise to plain dicts to keep the JSON response schema stable
    # regardless of what type get_history() returns.
    serialised = [
        {"role": msg["role"], "content": msg["content"]} for msg in history
    ]

    return JSONResponse(
        content={
            "session_id": session_id,
            "history": serialised,
            "message_count": len(serialised),
        }
    )


@router.delete(
    "/memory/{session_id}",
    summary="Clear conversation history for a session",
)
def clear_session_history(session_id: str) -> JSONResponse:
    """
    Permanently removes all stored messages for the given *session_id*.
    Returns the number of messages that were deleted so the caller can
    confirm the operation had effect.
    """
    # Fetch count before clearing so we can report it
    try:
        message_count = len(get_history(session_id, limit=50))
    except Exception as exc:
        logger.warning(
            "Could not pre-fetch history count for session '%s': %s", session_id, exc
        )
        message_count = 0

    try:
        message_count = clear_history(session_id) or message_count
    except Exception as exc:
        logger.exception(
            "Failed to clear history for session '%s': %s", session_id, exc
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear conversation history: {exc}",
        ) from exc

    logger.info("Cleared %d messages for session '%s'", message_count, session_id)
    return JSONResponse(
        content={
            "success": True,
            "session_id": session_id,
            "message": f"Cleared {message_count} messages",
        }
    )
