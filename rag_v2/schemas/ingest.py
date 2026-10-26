"""
rag_v2/schemas/ingest.py
------------------------
Pydantic v2 models for document ingestion responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    """Metadata record for a single ingested document.

    Stored in ``rag_v2_documents`` and returned in listing endpoints.
    """

    id: str = Field(..., description="Unique document identifier (UUID or hash).")
    title: str = Field(..., description="Human-readable document title.")
    file_type: str = Field(
        ..., description="MIME type or extension, e.g. 'application/pdf' or 'pdf'."
    )
    source_url: Optional[str] = Field(
        default=None, description="Original URL if the document was fetched remotely."
    )
    file_size: Optional[int] = Field(
        default=None, description="File size in bytes."
    )
    chunk_count: int = Field(
        ..., description="Number of text chunks extracted from the document."
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp at which the document was ingested (UTC).",
    )

    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    """Response returned by the ingest endpoint after a successful upload.

    Includes a confirmation flag, document metadata, and a human-friendly
    status message.
    """

    success: bool = Field(..., description="Whether ingestion completed without error.")
    document_id: str = Field(..., description="Unique identifier of the stored document.")
    title: str = Field(..., description="Resolved document title.")
    file_type: str = Field(
        ..., description="Detected or provided file type / MIME type."
    )
    chunk_count: int = Field(
        ..., description="Total number of chunks stored for this document."
    )
    message: str = Field(
        ..., description="Human-readable status or error message."
    )
