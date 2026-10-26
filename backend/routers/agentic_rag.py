"""
routers/agentic_rag.py — Agentic RAG Router (Backend 2 — Port 8001)
====================================================================
Exposes POST /api/agentic-rag — multi-step agentic LLM reasoning with
tool calling, memory, and retrieved knowledge base context.

This router is mounted ONLY on tool_server.py (Port 8001).
"""

import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from backend.rag.agentic_generator import agentic_query

logger = logging.getLogger("voicerag.routers.agentic_rag")

router = APIRouter()


class AgenticRAGRequest(BaseModel):
    query: str
    sessionId: str = "default"
    topK: int = 8
    apiKey: Optional[str] = None


@router.post("/api/agentic-rag")
def agentic_rag_endpoint(req: AgenticRAGRequest):
    """
    Agentic RAG endpoint — multi-step LLM reasoning with tool access.

    The LLM may call tools (weather, orders, students, web search, SQL, math)
    across multiple rounds before producing a final synthesized answer.

    Request body:
        query:     User question (Sinhala or English)
        sessionId: Conversation session ID
        topK:      Number of knowledge-base chunks to retrieve (default 8)
        apiKey:    Optional Gemini or OpenAI API key override
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty.")

    try:
        result = agentic_query(
            user_query=req.query.strip(),
            session_id=req.sessionId,
            top_k=req.topK,
            custom_api_key=req.apiKey,
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error("Agentic RAG error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Agentic RAG pipeline failed: {exc}",
        )
