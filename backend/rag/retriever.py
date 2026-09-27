"""
rag/retriever.py — Hybrid Vector & BM25 Search Engine
=======================================================
Provides search_similar_chunks() — a cross-lingual Reciprocal Rank Fusion
(RRF) search over:
  1. PostgreSQL HNSW vector index (pgvector ``<=>`` cosine operator)
  2. SQLite cosine-similarity fallback for offline / dev mode
  3. BM25 sparse keyword ranking over SQLite stored chunks
"""

import re
import json
import sqlite3
import logging
from typing import Dict, List, Optional, Any

from backend.db import (
    get_db_connection,
    cosine_similarity,
    SQLITE_DB_PATH,
)

logger = logging.getLogger("voicerag.rag.retriever")


# ---------------------------------------------------------------------------
# BM25 sparse keyword search (SQLite)
# ---------------------------------------------------------------------------

def _bm25_search(query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """Approximate BM25 keyword ranking over all SQLite rag_document_chunks."""
    tokens = [w.lower() for w in re.findall(r"\w+", query_text) if len(w) > 2]
    if not tokens:
        return []

    results = []
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.document_id, d.title, c.content, c.chunk_index
            FROM rag_document_chunks c
            JOIN rag_documents d ON c.document_id = d.id;
        """)
        rows = cur.fetchall()
        conn.close()

        scored_chunks = []
        for r in rows:
            content_lower = r[3].lower()
            score = 0.0
            for token in tokens:
                count = content_lower.count(token)
                if count > 0:
                    score += (count * 1.8) / (count + 0.5)

            if score > 0:
                scored_chunks.append({
                    "id": r[0],
                    "documentId": r[1],
                    "documentTitle": r[2],
                    "content": r[3],
                    "chunkIndex": r[4],
                    "score": score,
                })

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        results = scored_chunks[:top_k]
    except Exception as e:
        logger.debug(f"SQLite BM25 search note: {e}")

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_similar_chunks(
    query_embedding: List[float],
    top_k: int = 8,
    query_text: Optional[str] = None,
    custom_api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Hybrid dense + sparse search with Reciprocal Rank Fusion (RRF).

    Search order:
      1. PostgreSQL pgvector HNSW cosine search (if connected).
      2. SQLite cosine-similarity scan as dense fallback.
      3. BM25 keyword search over SQLite chunks.
      4. RRF fusion of dense + sparse lists, returning ``top_k`` results.

    Args:
        query_embedding: Pre-computed query vector.
        top_k:           Number of final results to return.
        query_text:      Original query string for BM25 (optional).
        custom_api_key:  Unused — kept for API symmetry.

    Returns:
        List of chunk dicts with keys: id, documentId, documentTitle,
        content, chunkIndex, similarity.
    """
    query_str = query_text or ""
    dense_results: List[Dict[str, Any]] = []

    # 1. PostgreSQL HNSW cosine vector search
    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    vector_str = f"[{','.join(map(str, query_embedding))}]"
                    vector_query = """
                        SELECT
                            c.id,
                            c.document_id,
                            d.title AS document_title,
                            c.content,
                            c.chunk_index,
                            1 - (c.embedding <=> %s::vector) AS similarity
                        FROM document_chunks c
                        JOIN documents d ON c.document_id = d.id
                        ORDER BY c.embedding <=> %s::vector
                        LIMIT %s;
                    """
                    cur.execute(vector_query, (vector_str, vector_str, top_k * 2))
                    rows = cur.fetchall()
                    for row in rows:
                        dense_results.append({
                            "id": str(row[0]),
                            "documentId": str(row[1]),
                            "documentTitle": row[2],
                            "content": row[3],
                            "chunkIndex": row[4],
                            "similarity": float(row[5]),
                        })
            except Exception as e:
                logger.debug(f"PostgreSQL vector search note: {e}")

    # 2. SQLite cosine-similarity fallback
    if not dense_results:
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                SELECT c.id, c.document_id, d.title, c.content, c.chunk_index, c.embedding
                FROM rag_document_chunks c
                JOIN rag_documents d ON c.document_id = d.id;
            """)
            rows = cur.fetchall()
            conn.close()

            scored = []
            for r in rows:
                try:
                    chunk_emb = json.loads(r[5])
                    sim = cosine_similarity(query_embedding, chunk_emb)
                    scored.append({
                        "id": r[0],
                        "documentId": r[1],
                        "documentTitle": r[2],
                        "content": r[3],
                        "chunkIndex": r[4],
                        "similarity": sim,
                    })
                except Exception:
                    continue

            scored.sort(key=lambda x: x["similarity"], reverse=True)
            dense_results = scored[: top_k * 2]
        except Exception as e:
            logger.debug(f"SQLite vector search note: {e}")

    # 3. BM25 keyword search
    bm25_results = _bm25_search(query_str, top_k=top_k)

    # 4. Reciprocal Rank Fusion
    rrf_scores: Dict[str, float] = {}
    items_map: Dict[str, Dict[str, Any]] = {}
    k_constant = 60.0

    for rank, item in enumerate(dense_results):
        item_id = item["id"]
        rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + (1.0 / (k_constant + rank + 1))
        items_map[item_id] = item

    for rank, item in enumerate(bm25_results):
        item_id = item["id"]
        rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + (1.0 / (k_constant + rank + 1))
        if item_id not in items_map:
            items_map[item_id] = {
                "id": item["id"],
                "documentId": item["documentId"],
                "documentTitle": item["documentTitle"],
                "content": item["content"],
                "chunkIndex": item["chunkIndex"],
                "similarity": 0.85,
            }

    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    final_chunks = [items_map[cid] for cid in sorted_ids[:top_k]]

    return final_chunks if final_chunks else dense_results[:top_k]
