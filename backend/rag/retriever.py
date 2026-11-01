"""
rag/retriever.py — Hybrid Vector & BM25 Search Engine + MMR Diversity Filter
==============================================================================
Provides:
  - search_similar_chunks()  — Hybrid RRF search (dense + BM25)
  - mmr_filter()             — Maximal Marginal Relevance diversity re-ranking

Search order:
  1. PostgreSQL HNSW vector index (pgvector ``<=>`` cosine operator)
  2. SQLite cosine-similarity fallback for offline / dev mode
  3. BM25 sparse keyword ranking over SQLite stored chunks
  4. RRF fusion → MMR diversity filter (for Pure-RAG mode)
"""

import re
import json
import math
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
# MMR — Maximal Marginal Relevance Diversity Filter
# ---------------------------------------------------------------------------

def _dot(a: List[float], b: List[float]) -> float:
    """Fast dot product of two equal-length float lists."""
    return sum(x * y for x, y in zip(a, b))


def _norm(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _cosine(a: List[float], b: List[float]) -> float:
    na, nb = _norm(a), _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return _dot(a, b) / (na * nb)


def mmr_filter(
    candidates: List[Dict[str, Any]],
    query_embedding: List[float],
    top_n: int = 5,
    lambda_param: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    Maximal Marginal Relevance (MMR) diversity filter.

    Selects ``top_n`` chunks that balance:
      - Relevance to the query   (weight = lambda_param,       default 70 %)
      - Diversity from each other (weight = 1 - lambda_param,  default 30 %)

    This prevents the LLM from seeing five near-identical chunks and instead
    surfaces a diverse, non-redundant set of evidence passages.

    Algorithm:
        MMR score = λ · sim(chunk, query) − (1−λ) · max_sim(chunk, already_selected)

    Args:
        candidates:      Ranked list of chunk dicts (must have 'content' key).
        query_embedding: Query vector for relevance scoring.
        top_n:           Number of chunks to return.
        lambda_param:    Trade-off weight (0 = max diversity, 1 = max relevance).

    Returns:
        Filtered list of ``top_n`` chunk dicts in MMR-selected order.
    """
    if not candidates:
        return []
    if len(candidates) <= top_n:
        return candidates

    # Build simple TF-IDF-like embeddings from content text for inter-chunk similarity.
    # We use the stored similarity score as a proxy for relevance to the query.
    selected: List[Dict[str, Any]] = []
    remaining = list(candidates)

    while len(selected) < top_n and remaining:
        best_idx = -1
        best_score = float("-inf")

        for i, chunk in enumerate(remaining):
            relevance = chunk.get("similarity", 0.5)

            # Max similarity to already-selected chunks (using content overlap as proxy)
            if not selected:
                redundancy = 0.0
            else:
                redundancy = max(
                    _content_overlap(chunk["content"], sel["content"])
                    for sel in selected
                )

            mmr_score = lambda_param * relevance - (1 - lambda_param) * redundancy
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        if best_idx == -1:
            break

        selected.append(remaining.pop(best_idx))

    logger.debug(
        "MMR filter: %d candidates → %d selected (λ=%.2f)",
        len(candidates) + len(selected),
        len(selected),
        lambda_param,
    )
    return selected


def _content_overlap(a: str, b: str) -> float:
    """Fast Jaccard token overlap between two text strings (0.0 – 1.0)."""
    set_a = set(re.findall(r"\w+", a.lower()))
    set_b = set(re.findall(r"\w+", b.lower()))
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


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

    # 1. PostgreSQL HNSW cosine vector search (skipped when no embedding is available)
    with get_db_connection() as conn:
        if conn and query_embedding:
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
    if not dense_results and query_embedding:
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
