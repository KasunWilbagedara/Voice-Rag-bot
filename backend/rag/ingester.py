"""
rag/ingester.py — Document Ingestion Pipeline
===============================================
Handles the full ingestion flow for a single document:
  1. Recursive structural chunking (via chunker.py)
  2. Batch embedding generation (via embedder.py)
  3. Persistence to SQLite (rag_documents / rag_document_chunks)
  4. Persistence to PostgreSQL pgvector (document_chunks) if connected
  5. In-memory cache update

Also provides ``save_chat_history()`` for dual-path (SQLite + PostgreSQL)
chat history persistence.
"""

import uuid
import json
import sqlite3
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.db import (
    get_db_connection,
    in_memory_store,
    SQLITE_DB_PATH,
)
from backend.rag.chunker import recursive_structural_chunk
from backend.rag.embedder import get_embeddings_batch

logger = logging.getLogger("voicerag.rag.ingester")


def ingest_document(
    title: str,
    file_type: str,
    content: str,
    custom_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full document ingestion pipeline.

    Steps:
      1. Chunk ``content`` into semantically-bounded segments.
      2. Batch-embed all chunks with the configured embedding model.
      3. Persist to SQLite (always) and PostgreSQL pgvector (if connected).
      4. Update the in-memory vector cache.

    Args:
        title:          Human-readable document name / filename.
        file_type:      MIME type or extension string (e.g. ``"text/plain"``).
        content:        Full raw document text.
        custom_api_key: Optional per-request embedding API key.

    Returns:
        ``{"documentId", "title", "chunkCount", "totalCharacters"}``

    Raises:
        ValueError: If *content* produces no parseable chunks.
    """
    raw_chunks = recursive_structural_chunk(content)
    if not raw_chunks:
        raise ValueError("Document content is empty or contains no parseable text.")

    embeddings = get_embeddings_batch(raw_chunks, custom_api_key)
    doc_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"

    # 1. SQLite persistence
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO rag_documents (id, title, file_type, created_at) VALUES (?, ?, ?, ?);",
            (doc_id, title, file_type, created_at),
        )
        for i, (chunk, emb) in enumerate(zip(raw_chunks, embeddings)):
            chunk_id = str(uuid.uuid4())
            emb_json = json.dumps(emb)
            cur.execute(
                """INSERT INTO rag_document_chunks
                   (id, document_id, content, chunk_index, embedding, created_at)
                   VALUES (?, ?, ?, ?, ?, ?);""",
                (chunk_id, doc_id, chunk, i, emb_json, created_at),
            )
        conn.commit()
        conn.close()
        logger.info(
            "Ingested document '%s' into SQLite (%d chunks).", title, len(raw_chunks)
        )
    except Exception as e:
        logger.error(f"Error persisting document to SQLite: {e}")

    # 2. PostgreSQL pgvector persistence (if connected)
    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO documents (id, title, file_type, created_at) "
                        "VALUES (%s, %s, %s, %s)",
                        (doc_id, title, file_type, created_at),
                    )
                    for i, (chunk, emb) in enumerate(zip(raw_chunks, embeddings)):
                        chunk_id = str(uuid.uuid4())
                        vector_str = f"[{','.join(map(str, emb))}]"
                        cur.execute(
                            """INSERT INTO document_chunks
                               (id, document_id, content, chunk_index, embedding, created_at)
                               VALUES (%s, %s, %s, %s, %s::vector, %s)""",
                            (chunk_id, doc_id, chunk, i, vector_str, created_at),
                        )
                    conn.commit()
                    logger.info(
                        "Ingested document '%s' into PostgreSQL.", title
                    )
            except Exception as e:
                conn.rollback()
                logger.warning(f"PostgreSQL ingestion note: {e}")

    # 3. In-memory cache
    in_memory_store.documents.append({
        "id": doc_id,
        "title": title,
        "file_type": file_type,
        "created_at": created_at,
    })
    for i, (chunk, emb) in enumerate(zip(raw_chunks, embeddings)):
        in_memory_store.chunks.append({
            "id": str(uuid.uuid4()),
            "document_id": doc_id,
            "content": chunk,
            "chunk_index": i,
            "embedding": emb,
            "created_at": created_at,
        })

    return {
        "documentId": doc_id,
        "title": title,
        "chunkCount": len(raw_chunks),
        "totalCharacters": len(content),
    }


def save_chat_history(
    user_query_text: str,
    retrieved_chunks: List[Dict[str, Any]],
    ai_response_text: str,
) -> None:
    """
    Persists a completed Q&A turn to both SQLite and PostgreSQL.

    Args:
        user_query_text:  The user's query string.
        retrieved_chunks: List of chunk dicts that were used in the response.
        ai_response_text: The generated answer text.
    """
    chat_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"
    chunks_json = json.dumps(retrieved_chunks)

    # SQLite
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO rag_chat_history
               (id, user_query_text, retrieved_chunks, ai_response_text, created_at)
               VALUES (?, ?, ?, ?, ?);""",
            (chat_id, user_query_text, chunks_json, ai_response_text, created_at),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"SQLite chat history save note: {e}")

    # PostgreSQL
    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO chat_history
                           (id, user_query_text, retrieved_chunks, ai_response_text, created_at)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (chat_id, user_query_text, chunks_json, ai_response_text, created_at),
                    )
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.debug(f"PostgreSQL chat history save note: {e}")

    in_memory_store.chat_history.append({
        "id": chat_id,
        "user_query_text": user_query_text,
        "retrieved_chunks": retrieved_chunks,
        "ai_response_text": ai_response_text,
        "created_at": created_at,
    })
