"""
rag/pipeline.py — Shared RAG turn runner
=========================================
One place that maps the frontend's backend mode (``x-backend-mode`` header)
to the right pipeline, so the text endpoint (/api/rag) and the voice endpoint
(/api/voice-pipeline) behave identically:

  pure      → hybrid search (12 candidates) → MMR diversity filter (top 5)
              → strictly grounded LLM, no tool enrichment
  standard  → hybrid search (8) → LLM with contextual tool enrichment
  tools     → agentic multi-step LLM loop with tool calling
"""

import logging
from typing import Any, Dict, List, Optional

from backend.rag.embedder import get_text_embedding
from backend.rag.generator import query_rag
from backend.rag.retriever import mmr_filter, search_similar_chunks

logger = logging.getLogger("voicerag.rag.pipeline")

VALID_MODES = ("pure", "standard", "tools")


def normalize_mode(raw_mode: Optional[str], default: str = "standard") -> str:
    """Maps an ``x-backend-mode`` header value to a known mode."""
    mode = (raw_mode or "").strip().lower()
    return mode if mode in VALID_MODES else default


def safe_query_embedding(text: str, custom_api_key: Optional[str] = None) -> List[float]:
    """Embeds *text*; returns [] on failure so retrieval degrades to keyword (BM25) search."""
    try:
        return get_text_embedding(text, custom_api_key)
    except Exception as e:
        logger.warning("Query embedding failed, falling back to keyword search only: %s", e)
        return []


def run_rag_turn(
    user_query: str,
    mode: str,
    custom_api_key: Optional[str] = None,
    model_name: str = "gemini-3.5-flash",
    target_language: str = "si",
    conversation_history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    session_id: str = "default_user",
) -> Dict[str, Any]:
    """
    Runs one question/answer turn in the requested *mode*.

    Returns ``{"answer", "retrievedChunks", "mode", "toolCalls"}``.
    Does not persist chat history — callers do that once they have the answer.
    """
    if mode == "tools":
        # Imported lazily: the agentic loop pulls in the tool registry.
        from backend.rag.agentic_generator import agentic_query

        result = agentic_query(
            user_query=user_query,
            session_id=session_id,
            top_k=8,
            custom_api_key=custom_api_key,
        )
        return {
            "answer": result.get("answer", ""),
            "retrievedChunks": result.get("retrievedChunks", []),
            "mode": "tools",
            "toolCalls": result.get("toolCalls", []),
        }

    pure = mode == "pure"
    query_embedding = safe_query_embedding(user_query, custom_api_key)
    retrieved = search_similar_chunks(
        query_embedding=query_embedding,
        top_k=12 if pure else 8,
        query_text=user_query,
        custom_api_key=custom_api_key,
    )
    if pure:
        retrieved = mmr_filter(retrieved, query_embedding, top_n=5, lambda_param=0.7)

    rag_res = query_rag(
        user_query=user_query,
        retrieved_chunks=retrieved,
        custom_api_key=custom_api_key,
        model_name=model_name,
        target_language=target_language,
        conversation_history=conversation_history,
        provider=provider,
        base_url=base_url,
        session_id=session_id,
        pure_rag_mode=pure,
    )
    return {
        "answer": rag_res["answer"],
        "retrievedChunks": rag_res["retrievedChunks"],
        "mode": mode,
        "toolCalls": [],
    }
