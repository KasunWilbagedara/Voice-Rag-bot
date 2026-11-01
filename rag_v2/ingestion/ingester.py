"""
rag_v2/ingestion/ingester.py
-----------------------------
Document ingestion pipeline.

Workflow
--------
1. Parse raw bytes / URL into text (via parser.py).
2. Chunk the text with recursive_chunk().
3. Embed all chunks via get_embeddings_batch().
4. Persist the document record and all chunk rows to PostgreSQL.
"""

import logging
import uuid
from typing import Dict, Optional

import psycopg2.extras

from rag_v2.config import CHUNK_TARGET_SIZE, CHUNK_OVERLAP, get_api_key
from rag_v2.core import recursive_chunk, get_embeddings_batch
from rag_v2.storage.db import get_db_connection
from rag_v2.ingestion.parser import parse_file, parse_url

logger = logging.getLogger("rag_v2.ingestion.ingester")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _embedding_to_pg_vector(embedding: list) -> str:
    """Convert a Python list of floats to the pgvector string format ``[0.1, 0.2, ...]``."""
    return "[" + ", ".join(str(float(v)) for v in embedding) + "]"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def ingest_text(
    text: str,
    title: str,
    file_type: str,
    api_key: Optional[str] = None,
    source_url: Optional[str] = None,
) -> Dict:
    """Chunk, embed, and store *text* in the RAG v2 database.

    Parameters
    ----------
    text:
        The full document text to ingest.
    title:
        Human-readable title stored in the ``rag_v2_documents`` table.
    file_type:
        Extension or format identifier (e.g. ``'.pdf'``, ``'url'``).
    api_key:
        Gemini / embedding API key.  Falls back to ``get_api_key()`` when
        ``None``.
    source_url:
        Optional origin URL stored alongside the document record.

    Returns
    -------
    Dict
        ``{document_id, title, file_type, chunk_count, success: True}``

    Raises
    ------
    RuntimeError
        If embedding generation or database operations fail.
    """
    resolved_key = api_key or get_api_key()

    # ── Step 1: Chunk ────────────────────────────────────────────────────────
    logger.info(
        "Chunking text for '%s' (len=%d, target=%d, overlap=%d)",
        title,
        len(text),
        CHUNK_TARGET_SIZE,
        CHUNK_OVERLAP,
    )
    chunks: list[str] = recursive_chunk(text, CHUNK_TARGET_SIZE, CHUNK_OVERLAP)
    chunk_count = len(chunks)
    logger.info("Produced %d chunks for '%s'.", chunk_count, title)

    if chunk_count == 0:
        raise ValueError(f"Document '{title}' produced zero chunks – aborting ingestion.")

    # ── Step 2: Generate document ID ────────────────────────────────────────
    doc_id = str(uuid.uuid4())

    # ── Step 3: Embed ────────────────────────────────────────────────────────
    logger.info("Generating embeddings for %d chunks …", chunk_count)
    embeddings: list[list[float]] = get_embeddings_batch(chunks, api_key=resolved_key)

    if len(embeddings) != chunk_count:
        raise RuntimeError(
            f"Embedding count mismatch: expected {chunk_count}, got {len(embeddings)}."
        )

    # ── Steps 4 & 5: Persist ────────────────────────────────────────────────
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # 4. Insert document record
                cur.execute(
                    """
                    INSERT INTO rag_v2_documents
                        (id, title, file_type, source_url, chunk_count)
                    VALUES
                        (%s, %s, %s, %s, %s)
                    """,
                    (doc_id, title, file_type, source_url, chunk_count),
                )
                logger.debug("Inserted document record id=%s", doc_id)

                # 5. Insert all chunk rows
                chunk_rows = [
                    (
                        str(uuid.uuid4()),   # chunk id
                        doc_id,              # document_id FK
                        chunk_text,          # content
                        chunk_idx,           # chunk_index
                        _embedding_to_pg_vector(embedding),  # embedding
                    )
                    for chunk_idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings))
                ]

                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO rag_v2_chunks
                        (id, document_id, content, chunk_index, embedding)
                    VALUES %s
                    """,
                    chunk_rows,
                    template="(%s, %s, %s, %s, %s::vector)",
                )
                logger.info(
                    "Inserted %d chunks for document id=%s.", chunk_count, doc_id
                )
    except Exception as exc:
        logger.error("Database error during ingestion of '%s': %s", title, exc)
        raise RuntimeError(f"Ingestion failed for '{title}': {exc}") from exc
    finally:
        conn.close()

    return {
        "document_id": doc_id,
        "title": title,
        "file_type": file_type,
        "chunk_count": chunk_count,
        "success": True,
    }


def ingest_file(
    file_bytes: bytes,
    filename: str,
    api_key: Optional[str] = None,
) -> Dict:
    """Parse *file_bytes* then ingest the resulting text.

    Parameters
    ----------
    file_bytes:
        Raw file content.
    filename:
        Original filename – used to detect format and as the document title.
    api_key:
        Optional embedding API key.

    Returns
    -------
    Dict
        Result from :func:`ingest_text`.
    """
    import os

    ext = os.path.splitext(filename)[1].lower()
    logger.info("ingest_file: '%s' (ext=%s, size=%d bytes)", filename, ext, len(file_bytes))

    text = parse_file(file_bytes, filename)
    return ingest_text(
        text=text,
        title=filename,
        file_type=ext,
        api_key=api_key,
    )


def ingest_url(url: str, api_key: Optional[str] = None) -> Dict:
    """Scrape *url* then ingest the resulting text.

    Parameters
    ----------
    url:
        Fully-qualified URL to ingest.
    api_key:
        Optional embedding API key.

    Returns
    -------
    Dict
        Result from :func:`ingest_text`.
    """
    logger.info("ingest_url: %s", url)
    text = parse_url(url)
    return ingest_text(
        text=text,
        title=url,
        file_type="url",
        api_key=api_key,
        source_url=url,
    )
