import logging
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from backend.rag import save_chat_history
from backend.rag.pipeline import normalize_mode, run_rag_turn

router = APIRouter(prefix="/api/rag", tags=["RAG"])
logger = logging.getLogger("voicerag.rag_router")


class RagQueryRequest(BaseModel):
    query: str
    apiKey: Optional[str] = None
    model: Optional[str] = "gemini-3.5-flash"
    provider: Optional[str] = None
    baseUrl: Optional[str] = None
    language: Optional[str] = "si"
    conversationHistory: Optional[List[Dict[str, str]]] = None
    sessionId: Optional[str] = "default_user"


@router.post("")
def process_rag_query(
    req: RagQueryRequest,
    x_backend_mode: Optional[str] = Header(default=None, alias="x-backend-mode"),
):
    """
    Text RAG query endpoint.

    ``x-backend-mode`` header:
      - ``pure``   → hybrid search + MMR diversity filter, strictly grounded
                     LLM with no tool enrichment
      - ``tools``  → agentic multi-step LLM with tool calling
      - absent     → standard RAG with contextual tool enrichment
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query text is required.")

    mode = normalize_mode(x_backend_mode)
    session_id = req.sessionId or "default_user"
    logger.info("RAG query | mode=%s | session=%s | query_len=%d", mode, session_id, len(req.query))

    try:
        result = run_rag_turn(
            user_query=req.query,
            mode=mode,
            custom_api_key=req.apiKey,
            model_name=req.model or "gemini-3.5-flash",
            target_language=req.language or "si",
            conversation_history=req.conversationHistory,
            provider=req.provider,
            base_url=req.baseUrl,
            session_id=session_id,
        )
        save_chat_history(req.query, result["retrievedChunks"], result["answer"], session_id)

        return {
            "query": req.query,
            "answer": result["answer"],
            "retrievedChunks": result["retrievedChunks"],
            "toolCalls": result["toolCalls"],
            "mode": "pure-rag" if mode == "pure" else mode,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("RAG Pipeline Error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
