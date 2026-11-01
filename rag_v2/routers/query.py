"""
RAG query router for RAG v2 — supports both streaming and batch responses.

Exposes:
  POST /api/v2/query  — run a RAG query (streaming or non-streaming)
  GET  /api/v2/tools  — list registered tool-calling functions
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from rag_v2.core.pipeline import RAGPipeline
from rag_v2.schemas import QueryRequest, QueryResponse
from rag_v2.tools import list_tools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["Query"])


@router.post(
    "/query",
    summary="Run a RAG query",
    response_model=None,  # response_model varies (streaming vs batch)
)
async def query_rag(request: QueryRequest):
    """
    Execute a retrieval-augmented generation query.

    * When ``stream=true`` the endpoint returns a **text/event-stream**
      (Server-Sent Events) where each chunk is a partial answer token.
    * When ``stream=false`` (default) the endpoint waits for the full
      answer and returns a :class:`QueryResponse` JSON object.

    Optional ``api_key`` overrides the server-side key for this request.
    """
    # ------------------------------------------------------------------ #
    # Validate query
    # ------------------------------------------------------------------ #
    query = (request.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    session_id = request.session_id or "default"
    top_k = request.top_k if request.top_k is not None else 5
    rerank_top_n = request.rerank_top_n if request.rerank_top_n is not None else 3

    # ------------------------------------------------------------------ #
    # Build pipeline
    # ------------------------------------------------------------------ #
    try:
        pipeline = RAGPipeline(api_key=request.api_key)
    except Exception as exc:
        logger.exception("Failed to initialise RAGPipeline: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline initialisation error: {exc}",
        ) from exc

    # ------------------------------------------------------------------ #
    # Streaming response
    # ------------------------------------------------------------------ #
    if request.stream:
        logger.info(
            "Streaming query | session=%s top_k=%d rerank=%d",
            session_id, top_k, rerank_top_n,
        )

        async def _event_stream():
            try:
                async for chunk in pipeline.run_stream(
                    query=query,
                    session_id=session_id,
                    top_k=top_k,
                    rerank_top_n=rerank_top_n,
                ):
                    yield chunk
            except Exception as stream_exc:
                logger.exception("Streaming pipeline error: %s", stream_exc)
                # Emit an error event so the client can surface it
                yield f"event: error\ndata: {stream_exc}\n\n"

        return StreamingResponse(
            _event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ------------------------------------------------------------------ #
    # Non-streaming (batch) response
    # ------------------------------------------------------------------ #
    logger.info(
        "Batch query | session=%s top_k=%d rerank=%d",
        session_id, top_k, rerank_top_n,
    )
    try:
        result = await pipeline.run(
            query=query,
            session_id=session_id,
            top_k=top_k,
            rerank_top_n=rerank_top_n,
        )
    except Exception as exc:
        logger.exception("Batch pipeline error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {exc}",
        ) from exc

    return QueryResponse(**result)


@router.get("/tools", summary="List registered tool-calling functions")
async def get_tools():
    """
    Returns the list of tool definitions available to the LLM during
    tool-calling / function-calling rounds.
    """
    tools = list_tools()
    return {"tools": tools, "count": len(tools)}
