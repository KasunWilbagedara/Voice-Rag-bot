"""
Document management router for RAG v2.

Exposes:
  GET    /api/v2/documents                  — list all ingested documents
  GET    /api/v2/documents/{document_id}    — get a single document + chunk previews
  DELETE /api/v2/documents/{document_id}    — permanently delete a document and its chunks

The storage layer is synchronous psycopg2, so these are plain ``def`` endpoints
(FastAPI runs them in a worker thread).
"""

import logging
from typing import Any, Dict, List

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from rag_v2.schemas import DocumentInfo
from rag_v2.storage.db import require_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["Documents"])

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _row_to_document_info(row: Dict[str, Any]) -> DocumentInfo:
    """Convert a DB row mapping to a :class:`DocumentInfo`."""
    return DocumentInfo(
        id=str(row["id"]),
        title=row["title"],
        file_type=row["file_type"],
        source_url=row.get("source_url"),
        chunk_count=row["chunk_count"] or 0,
        created_at=row["created_at"],
    )


def _dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ---------------------------------------------------------------------------
# GET /api/v2/documents
# ---------------------------------------------------------------------------

@router.get(
    "/documents",
    summary="List all ingested documents",
)
def list_documents() -> JSONResponse:
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
        with require_db_connection() as conn, _dict_cursor(conn) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("Failed to list documents: %s", exc)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    documents: List[Dict[str, Any]] = [
        _row_to_document_info(row).model_dump(mode="json") for row in rows
    ]
    return JSONResponse(content={"documents": documents, "total": len(documents)})


# ---------------------------------------------------------------------------
# GET /api/v2/documents/{document_id}
# ---------------------------------------------------------------------------

@router.get(
    "/documents/{document_id}",
    summary="Get a document and its chunk previews",
)
def get_document(document_id: str) -> JSONResponse:
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
        with require_db_connection() as conn, _dict_cursor(conn) as cur:
            cur.execute(doc_sql, (document_id,))
            doc_row = cur.fetchone()
            if doc_row is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document '{document_id}' not found.",
                )
            cur.execute(chunks_sql, (document_id,))
            chunk_rows = cur.fetchall()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get document %s: %s", document_id, exc)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    chunks = [
        {
            "chunk_index": row["chunk_index"],
            "content_preview": row["content"][:200],
        }
        for row in chunk_rows
    ]

    return JSONResponse(
        content={
            "document": _row_to_document_info(doc_row).model_dump(mode="json"),
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
def delete_document(document_id: str) -> JSONResponse:
    """
    Permanently removes the document and every associated chunk from the
    database (``rag_v2_chunks`` cascades on ``document_id``).
    """
    try:
        with require_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rag_v2_documents WHERE id = %s", (document_id,))
                deleted = cur.rowcount
            conn.commit()
    except Exception as exc:
        logger.exception("Failed to delete document %s: %s", document_id, exc)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    logger.info("Deleted document %s", document_id)
    return JSONResponse(
        content={
            "success": True,
            "document_id": document_id,
            "message": "Document deleted successfully",
        }
    )
