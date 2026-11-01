"""
rag_v2/core/retriever.py
------------------------
Hybrid search engine combining pgvector (dense) and BM25 (sparse) retrieval,
fused via Reciprocal Rank Fusion (RRF).
"""

import logging
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi  # type: ignore

from rag_v2.storage.db import require_db_connection

logger = logging.getLogger("rag_v2.core.retriever")


# ---------------------------------------------------------------------------
# Dense (vector) search
# ---------------------------------------------------------------------------

def vector_search(
    query_embedding: List[float],
    top_k: int = 10,
    document_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Perform approximate nearest-neighbour search via pgvector.

    Parameters
    ----------
    query_embedding : List[float]
        Dense query vector.
    top_k : int
        Maximum number of results to return.
    document_ids : List[str], optional
        If provided, restrict search to these document IDs.

    Returns
    -------
    List[Dict]
        Each dict has keys: id, document_id, document_title, content,
        chunk_index, similarity, metadata.
    """
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    base_sql = """
        SELECT
            c.id,
            c.document_id,
            c.content,
            c.chunk_index,
            c.metadata,
            d.title AS document_title,
            (1 - (c.embedding <=> %s::vector)) AS similarity
        FROM rag_v2_chunks c
        JOIN rag_v2_documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
    """

    params: List[Any] = [embedding_str]

    if document_ids:
        placeholders = ",".join(["%s"] * len(document_ids))
        base_sql += f" AND c.document_id IN ({placeholders})"
        params.extend(document_ids)

    base_sql += " ORDER BY c.embedding <=> %s::vector ASC LIMIT %s"
    params.append(embedding_str)
    params.append(top_k)

    results: List[Dict[str, Any]] = []
    try:
        with require_db_connection() as conn, conn.cursor() as cur:
            cur.execute(base_sql, params)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            for row in rows:
                record = dict(zip(cols, row))
                # Normalise metadata: ensure it's a dict
                meta = record.get("metadata")
                if isinstance(meta, str):
                    try:
                        record["metadata"] = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        record["metadata"] = {}
                elif meta is None:
                    record["metadata"] = {}
                results.append(record)
        logger.debug("vector_search returned %d results", len(results))
    except Exception as exc:  # noqa: BLE001
        logger.error("vector_search failed: %s", exc, exc_info=True)

    return results


# ---------------------------------------------------------------------------
# Sparse (BM25) search
# ---------------------------------------------------------------------------

def bm25_search(
    query: str,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Perform BM25 keyword search over all stored chunks.

    Parameters
    ----------
    query : str
        The query string.
    top_k : int
        Maximum number of results to return.

    Returns
    -------
    List[Dict]
        Each dict has keys: id, document_id, document_title, content,
        chunk_index, metadata, bm25_score.
    """
    fetch_sql = """
        SELECT
            c.id,
            c.document_id,
            c.content,
            c.chunk_index,
            c.metadata,
            d.title AS document_title
        FROM rag_v2_chunks c
        JOIN rag_v2_documents d ON c.document_id = d.id
        ORDER BY c.document_id, c.chunk_index
    """

    all_chunks: List[Dict[str, Any]] = []
    try:
        with require_db_connection() as conn, conn.cursor() as cur:
            cur.execute(fetch_sql)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            for row in rows:
                record = dict(zip(cols, row))
                meta = record.get("metadata")
                if isinstance(meta, str):
                    try:
                        record["metadata"] = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        record["metadata"] = {}
                elif meta is None:
                    record["metadata"] = {}
                all_chunks.append(record)
    except Exception as exc:  # noqa: BLE001
        logger.error("bm25_search DB fetch failed: %s", exc, exc_info=True)
        return []

    if not all_chunks:
        logger.warning("bm25_search: no chunks in database")
        return []

    # Tokenize
    tokenized_corpus = [
        chunk["content"].lower().split() for chunk in all_chunks
    ]
    query_tokens = query.lower().split()

    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query_tokens)

    # Attach scores and sort
    scored: List[Dict[str, Any]] = []
    for chunk, score in zip(all_chunks, scores):
        entry = dict(chunk)
        entry["bm25_score"] = float(score)
        scored.append(entry)

    scored.sort(key=lambda x: x["bm25_score"], reverse=True)
    results = scored[:top_k]
    logger.debug("bm25_search returned %d results", len(results))
    return results


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = 60,
) -> List[Dict[str, Any]]:
    """
    Merge vector and BM25 results using Reciprocal Rank Fusion.

    RRF score = Σ 1 / (k + rank_in_list)   for each result list

    Parameters
    ----------
    vector_results : List[Dict]
        Results from :func:`vector_search`.
    bm25_results : List[Dict]
        Results from :func:`bm25_search`.
    k : int
        RRF smoothing constant (default 60).

    Returns
    -------
    List[Dict]
        Merged list sorted by rrf_score descending.  Each dict has all
        original fields plus bm25_score and rrf_score.
    """
    fused: Dict[str, Dict[str, Any]] = {}

    def _process_list(result_list: List[Dict[str, Any]]) -> None:
        for rank, item in enumerate(result_list, start=1):
            chunk_id = str(item["id"])
            rrf_contribution = 1.0 / (k + rank)
            if chunk_id not in fused:
                fused[chunk_id] = dict(item)
                fused[chunk_id].setdefault("similarity", 0.0)
                fused[chunk_id].setdefault("bm25_score", 0.0)
                fused[chunk_id]["rrf_score"] = 0.0
            fused[chunk_id]["rrf_score"] += rrf_contribution
            # Preserve best scores from each source
            if "similarity" in item:
                fused[chunk_id]["similarity"] = max(
                    fused[chunk_id].get("similarity", 0.0),
                    item.get("similarity", 0.0),
                )
            if "bm25_score" in item:
                fused[chunk_id]["bm25_score"] = max(
                    fused[chunk_id].get("bm25_score", 0.0),
                    item.get("bm25_score", 0.0),
                )

    _process_list(vector_results)
    _process_list(bm25_results)

    merged = sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)
    logger.debug(
        "RRF merged %d vector + %d BM25 → %d unique chunks",
        len(vector_results),
        len(bm25_results),
        len(merged),
    )
    return merged


# ---------------------------------------------------------------------------
# Hybrid search (public API)
# ---------------------------------------------------------------------------

def hybrid_search(
    query: str,
    query_embedding: List[float],
    top_k: int = 10,
    document_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Run vector and BM25 search in parallel and fuse results via RRF.

    Parameters
    ----------
    query : str
        Raw query string (used for BM25).
    query_embedding : List[float]
        Dense query vector (used for vector search).
    top_k : int
        Number of final results to return after fusion.
    document_ids : List[str], optional
        Restrict vector search to these document IDs.

    Returns
    -------
    List[Dict]
        Top-k fused results, each with id, document_id, document_title,
        content, chunk_index, similarity, bm25_score, rrf_score, metadata.
    """
    vector_results: List[Dict[str, Any]] = []
    bm25_results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_vector = executor.submit(
            vector_search, query_embedding, top_k, document_ids
        )
        future_bm25 = executor.submit(bm25_search, query, top_k)

        for future in as_completed([future_vector, future_bm25]):
            if future is future_vector:
                try:
                    vector_results = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.error("vector_search thread failed: %s", exc, exc_info=True)
            else:
                try:
                    bm25_results = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.error("bm25_search thread failed: %s", exc, exc_info=True)

    fused = reciprocal_rank_fusion(vector_results, bm25_results)
    top = fused[:top_k]
    logger.info(
        "hybrid_search: query=%r → %d results (vector=%d, bm25=%d)",
        query[:60],
        len(top),
        len(vector_results),
        len(bm25_results),
    )
    return top
