"""
Document management router for RAG v2.

Exposes:
  GET    /api/v2/documents                  — list all ingested documents
  GET    /api/v2/documents/{document_id}    — get a single document + chunk previews
  DELETE /api/v2/documents/{document_id}    — permanently delete a document and its chunks
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from rag_v2.schemas import DocumentInfo
from rag_v2.storage.db import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["Documents"])

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _row_to_document_info(row) -> DocumentInfo:
    """Convert a DB row (tuple or mapping) to a :class:`DocumentInfo`."""
    return DocumentInfo(
        id=str(row["id"]),
        title=row["title"],
        file_type=row["file_type"],
        source_url=row.get("source_url"),
        chunk_count=row["chunk_count"],
        created_at=str(row["created_at"]),
    )


# ---------------------------------------------------------------------------
# GET /api/v2/documents
# ---------------------------------------------------------------------------

@router.get(
    "/documents",
    summary="List all ingested documents",
)
async def list_documents() -> JSONResponse:
    """
    Returns every document that has been ingested into the RAG system,
    ordered by most recent first.
    """
    sql = (
        "SELECT id, title, file_type, source_url, chunk_count, created_at "
        "FROM rag_v2_documents "
        "ORDER BY created_at DESC"
    )
    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
    except Exception as exc:
        logger.exception("Failed to list documents: %s", exc)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    documents: List[Dict[str, Any]] = [
        _row_to_document_info(row).model_dump() for row in rows
    ]
    return JSONResponse(content={"documents": documents, "total": len(documents)})


# ---------------------------------------------------------------------------
# GET /api/v2/documents/{document_id}
# ---------------------------------------------------------------------------

@router.get(
    "/documents/{document_id}",
    summary="Get a document and its chunk previews",
)
async def get_document(document_id: str) -> JSONResponse:
    """
    Fetches the document metadata and the first 200 characters of each
    stored chunk so callers can verify what was ingested.
    """
    doc_sql = (
        "SELECT id, title, file_type, source_url, chunk_count, created_at "
        "FROM rag_v2_documents "
        "WHERE id = %s"
    )
    chunks_sql = (
        "SELECT chunk_index, content "
        "FROM rag_v2_chunks "
        "WHERE document_id = %s "
        "ORDER BY chunk_index"
    )

    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                # Fetch document
                await cur.execute(doc_sql, (document_id,))
                doc_row = await cur.fetchone()

                if doc_row is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Document '{document_id}' not found.",
                    )

                # Fetch chunks
                await cur.execute(chunks_sql, (document_id,))
                chunk_rows = await cur.fetchall()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get document %s: %s", document_id, exc)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    doc_info = _row_to_document_info(doc_row)
    chunks = [
        {
            "chunk_index": row["chunk_index"],
            "content_preview": row["content"][:200],
        }
        for row in chunk_rows
    ]

    return JSONResponse(
        content={
            "document": doc_info.model_dump(),
            "chunks": chunks,
        }
    )


# ---------------------------------------------------------------------------
# DELETE /api/v2/documents/{document_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/documents/{document_id}",
    summary="Delete a document and all its chunks",
)
async def delete_document(document_id: str) -> JSONResponse:
    """
    Permanently removes the document and every associated chunk from the
    database. The ``rag_v2_chunks`` table must have a foreign-key cascade
    on ``document_id`` so chunks are cleaned up automatically.
    """
    check_sql = "SELECT id FROM rag_v2_documents WHERE id = %s"
    delete_sql = "DELETE FROM rag_v2_documents WHERE id = %s"

    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                # Verify existence first so we can return a proper 404
                await cur.execute(check_sql, (document_id,))
                if await cur.fetchone() is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Document '{document_id}' not found.",
                    )

                await cur.execute(delete_sql, (document_id,))
            await conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete document %s: %s", document_id, exc)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    logger.info("Deleted document %s", document_id)
    return JSONResponse(
        content={
            "success": True,
            "document_id": document_id,
            "message": "Document deleted successfully",
        }
    )
