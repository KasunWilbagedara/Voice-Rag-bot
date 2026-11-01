"""
Document ingestion router for RAG v2.

Exposes:
  POST /api/v2/ingest        — upload a file or provide a URL for ingestion
  GET  /api/v2/ingest/status — readiness probe for the ingestion subsystem
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from rag_v2.ingestion.ingester import ingest_file, ingest_url
from rag_v2.schemas import IngestResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["Ingestion"])


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest a document (file upload or URL)",
)
async def ingest_document(
    file: Optional[UploadFile] = File(default=None, description="Binary file to ingest"),
    url: Optional[str] = Form(default=None, description="Public URL of a document to ingest"),
    api_key: Optional[str] = Form(default=None, description="Override API key for this request"),
) -> IngestResponse:
    """
    Accepts **either** a file upload **or** a URL — never both and never neither.

    * File path: the raw bytes are read from the upload and forwarded to the
      ingestion pipeline together with the original filename so the correct
      parser can be selected.
    * URL path: the URL is fetched and parsed by the ingestion pipeline.

    Returns an :class:`IngestResponse` with the newly created document ID and
    the number of chunks that were stored.
    """
    # ------------------------------------------------------------------ #
    # Input validation
    # ------------------------------------------------------------------ #
    has_file = file is not None and file.filename
    has_url = url is not None and url.strip()

    if has_file and has_url:
        raise HTTPException(
            status_code=400,
            detail="Provide either a file OR a url — not both.",
        )

    if not has_file and not has_url:
        raise HTTPException(
            status_code=400,
            detail="You must provide either a file or a url to ingest.",
        )

    # ------------------------------------------------------------------ #
    # Ingestion
    # ------------------------------------------------------------------ #
    try:
        if has_file:
            file_bytes = await file.read()
            if not file_bytes:
                raise HTTPException(
                    status_code=400,
                    detail="The uploaded file is empty.",
                )
            logger.info("Ingesting file '%s' (%d bytes)", file.filename, len(file_bytes))
            result: IngestResponse = await ingest_file(
                file_bytes=file_bytes,
                filename=file.filename,
                api_key=api_key,
            )
        else:
            clean_url = url.strip()
            logger.info("Ingesting URL '%s'", clean_url)
            result: IngestResponse = await ingest_url(
                url=clean_url,
                api_key=api_key,
            )
    except HTTPException:
        # Re-raise validation HTTP exceptions as-is
        raise
    except Exception as exc:
        logger.exception("Ingestion failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {exc}",
        ) from exc

    return result


@router.get("/ingest/status", summary="Ingestion subsystem readiness")
async def ingest_status() -> JSONResponse:
    """Simple readiness probe — always returns ``ready: true`` when the service is up."""
    return JSONResponse(content={"service": "ingestion", "ready": True})
