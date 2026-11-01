import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from backend.rag import (
    get_text_embedding as get_embedding,
    search_similar_chunks as search_vector_database,
    query_rag as generate_voice_rag_answer,
    save_chat_history,
)
from backend.rag.retriever import mmr_filter

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
    RAG query endpoint for Backend 1 (Port 8000).

    Header ``x-backend-mode: pure``  → Pure RAG mode:
      - No tool calls
      - MMR diversity filter applied to retrieved chunks
      - LLM strictly grounded to document context only

    No header or ``x-backend-mode: tools`` → Standard RAG with tool enrichment.
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query text is required.")

    pure_mode = (x_backend_mode or "").lower() == "pure"
    logger.info(
        "RAG query | mode=%s | session=%s | query_len=%d",
        "pure-rag" if pure_mode else "standard",
        req.sessionId,
        len(req.query),
    )

    try:
        query_embedding = get_embedding(req.query, req.apiKey)
        retrieved_chunks = search_vector_database(
            query_embedding=query_embedding,
            top_k=12 if pure_mode else 8,   # Retrieve extra candidates for MMR
            query_text=req.query,
            custom_api_key=req.apiKey,
        )

        # Pure RAG: apply MMR diversity filter (70% relevance, 30% diversity)
        if pure_mode:
            retrieved_chunks = mmr_filter(
                candidates=retrieved_chunks,
                query_embedding=query_embedding,
                top_n=5,
                lambda_param=0.7,
            )

        rag_res = generate_voice_rag_answer(
            user_query=req.query,
            retrieved_chunks=retrieved_chunks,
            custom_api_key=req.apiKey,
            model_name=req.model or "gemini-3.5-flash",
            target_language=req.language or "si",
            conversation_history=req.conversationHistory,
            provider=req.provider,
            base_url=req.baseUrl,
            session_id=req.sessionId or "default_user",
            pure_rag_mode=pure_mode,
        )
        answer = rag_res["answer"]
        final_chunks = rag_res["retrievedChunks"]

        save_chat_history(req.query, final_chunks, answer)

        return {
            "query": req.query,
            "answer": answer,
            "retrievedChunks": final_chunks,
            "mode": "pure-rag" if pure_mode else "standard",
        }
    except Exception as e:
        logger.error("RAG Pipeline Error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
