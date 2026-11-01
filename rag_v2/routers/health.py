"""
Health check router for RAG v2.

Exposes:
  GET /health  — full health status
  GET /        — service info / redirect hint
"""

import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from rag_v2.config import PORT
from rag_v2.storage.db import is_db_connected

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
async def health_check() -> JSONResponse:
    """
    Returns the operational status of the RAG v2 service including
    database connectivity and LLM provider availability.
    """
    db_ok = await is_db_connected()

    # Determine LLM provider
    if os.getenv("GEMINI_API_KEY"):
        llm_provider = "gemini"
    elif os.getenv("OPENAI_API_KEY"):
        llm_provider = "openai"
    else:
        llm_provider = "not configured"

    payload = {
        "status": "healthy",
        "service": "RAG v2",
        "port": PORT,
        "db_connected": db_ok,
        "db_type": "PostgreSQL + pgvector" if db_ok else "unavailable",
        "llm_provider": llm_provider,
        "version": "2.0.0",
    }

    # Use 200 regardless so load-balancers don't kill the pod; clients can
    # inspect the individual flags.
    logger.debug("Health check result: %s", payload)
    return JSONResponse(content=payload)


@router.get("/", summary="Service info")
async def root() -> JSONResponse:
    """
    Returns basic service discovery information.
    Clients can use the `docs` URL to explore the interactive API.
    """
    return JSONResponse(
        content={
            "service": "RAG v2 — Retrieval-Augmented Generation API",
            "port": PORT,
            "docs": f"http://0.0.0.0:{PORT}/docs",
            "health": f"http://0.0.0.0:{PORT}/health",
        }
    )
