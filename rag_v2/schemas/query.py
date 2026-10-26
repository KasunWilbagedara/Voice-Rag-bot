"""
rag_v2/schemas/query.py
-----------------------
Pydantic v2 models for RAG query requests and responses (streaming + batch).
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A single source chunk that contributed to the generated answer."""

    document_id: str = Field(..., description="ID of the parent document.")
    document_title: str = Field(..., description="Human-readable title of the parent document.")
    chunk_index: int = Field(
        ..., description="Zero-based position of this chunk within its document."
    )
    content: str = Field(..., description="Raw text of the retrieved chunk.")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cosine similarity between the query embedding and this chunk (0–1).",
    )


class StreamChunk(BaseModel):
    """A single server-sent event (SSE) payload emitted during streaming.

    The ``type`` discriminator drives how the client renders each chunk:

    * ``"text"``        — incremental answer token(s).
    * ``"citation"``    — accompanying source references.
    * ``"tool_result"`` — output from an invoked tool / function.
    * ``"done"``        — end-of-stream sentinel; ``content`` may be empty.
    """

    type: Literal["text", "citation", "tool_result", "done"] = Field(
        ..., description="Payload discriminator."
    )
    content: str = Field(
        default="",
        description="Text content for 'text'/'tool_result' chunks, empty for others.",
    )
    citations: Optional[List[Citation]] = Field(
        default=None,
        description="Source citations, populated only when type == 'citation'.",
    )


class QueryRequest(BaseModel):
    """Incoming query from the client.

    All retrieval tuning parameters have sensible defaults so callers only
    need to supply ``query`` for basic usage.
    """

    query: str = Field(..., min_length=1, description="The user's natural-language question.")
    session_id: str = Field(
        default="default",
        description="Conversation session identifier used for history retrieval.",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Optional per-request API key override (e.g. for Gemini).",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of candidate chunks to retrieve from the vector store.",
    )
    rerank_top_n: int = Field(
        default=4,
        ge=1,
        le=50,
        description="Number of chunks to keep after re-ranking.",
    )
    include_citations: bool = Field(
        default=True,
        description="Whether to include source citations in the response.",
    )
    stream: bool = Field(
        default=True,
        description="If True, the response is streamed via SSE; otherwise a single JSON object is returned.",
    )


class QueryResponse(BaseModel):
    """Full (non-streaming) query response.

    Returned when ``QueryRequest.stream == False``.
    """

    answer: str = Field(..., description="The generated answer text.")
    citations: List[Citation] = Field(
        default_factory=list,
        description="Source chunks used to generate the answer.",
    )
    session_id: str = Field(
        ..., description="Echo of the session ID used for this query."
    )
    tool_results: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Structured results from any tools invoked during generation.",
    )
