import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.rag_service import (
    get_embedding,
    search_vector_database,
    generate_voice_rag_answer,
    save_chat_history,
)

router = APIRouter(prefix="/api/rag", tags=["RAG"])
logger = logging.getLogger("voicerag.rag_router")

from typing import Optional, List, Dict, Any

class RagQueryRequest(BaseModel):
    query: str
    apiKey: Optional[str] = None
    model: Optional[str] = "gemini-flash-latest"
    language: Optional[str] = "si"
    conversationHistory: Optional[List[Dict[str, str]]] = None

@router.post("")
def process_rag_query(req: RagQueryRequest):
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query text is required.")

    try:
        query_embedding = get_embedding(req.query, req.apiKey)
        retrieved_chunks = search_vector_database(
            query_embedding=query_embedding,
            top_k=8,
            query_text=req.query,
            custom_api_key=req.apiKey,
        )
        rag_res = generate_voice_rag_answer(
            user_query=req.query,
            retrieved_chunks=retrieved_chunks,
            custom_api_key=req.apiKey,
            model_name=req.model or "gemini-2.0-flash",
            target_language=req.language or "si",
            conversation_history=req.conversationHistory,
        )
        answer = rag_res["answer"]
        final_chunks = rag_res["retrievedChunks"]

        save_chat_history(req.query, final_chunks, answer)

        return {
            "query": req.query,
            "answer": answer,
            "retrievedChunks": final_chunks,
        }
    except Exception as e:
        logger.error(f"RAG Pipeline Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
