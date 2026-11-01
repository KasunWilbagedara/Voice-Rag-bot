"""
rag_v2/core/reranker.py
-----------------------
LLM-based reranker.

Sends all candidate chunks to the LLM in a single batch prompt and asks for
relevance scores (0-10). Chunks are then sorted by score and the top_n are
returned.  Falls back gracefully to returning the first top_n chunks if the
LLM call fails or produces un-parseable output.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from rag_v2.config import GEMINI_MODEL, get_api_key, is_gemini_key

logger = logging.getLogger("rag_v2.core.reranker")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_rerank_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
    """Build the batch scoring prompt sent to the LLM."""
    passages = "\n\n".join(
        f"[{i}] {chunk.get('content', '')[:500]}"
        for i, chunk in enumerate(chunks)
    )
    return (
        f"Query: {query}\n\n"
        f"Passages:\n{passages}\n\n"
        "Rate the relevance of each passage to the query on a scale 0-10. "
        "Return ONLY a JSON array of numbers like [8, 3, 7, ...] with one "
        f"score per passage. There are {len(chunks)} passages, so return "
        f"exactly {len(chunks)} scores."
    )


def _parse_scores(response_text: str, expected_count: int) -> Optional[List[float]]:
    """Extract a JSON float array from *response_text*."""
    # Try to find a JSON array anywhere in the response
    match = re.search(r"\[[\d\s.,]+\]", response_text)
    if not match:
        logger.warning("No JSON array found in reranker response: %r", response_text[:200])
        return None
    try:
        scores = json.loads(match.group())
        if not isinstance(scores, list):
            return None
        scores = [float(s) for s in scores]
        if len(scores) != expected_count:
            logger.warning(
                "Expected %d scores, got %d; will use what we have",
                expected_count,
                len(scores),
            )
            # Pad with 0s or truncate to match
            if len(scores) < expected_count:
                scores.extend([0.0] * (expected_count - len(scores)))
            else:
                scores = scores[:expected_count]
        return scores
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse reranker scores: %s", exc)
        return None


def _call_gemini(prompt: str, api_key: str) -> str:
    """Call the Gemini generative model and return the text response."""
    from google import genai  # type: ignore

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text or ""


def _call_openai(prompt: str, api_key: str) -> str:
    """Call the OpenAI chat completion and return the text response."""
    import openai  # type: ignore

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rerank(
    query: str,
    chunks: List[Dict[str, Any]],
    top_n: int = 4,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Rerank *chunks* by relevance to *query* using an LLM scorer.

    If len(chunks) <= top_n the chunks are returned as-is (no LLM call).
    On any failure the function falls back to returning the first *top_n*
    chunks unchanged.

    Parameters
    ----------
    query : str
        The user query.
    chunks : List[Dict]
        Candidate chunks from the retriever.  Each dict must have a
        'content' key.
    top_n : int
        Number of top chunks to return after reranking.
    api_key : str, optional
        API key; auto-resolved from config if omitted.

    Returns
    -------
    List[Dict]
        Up to *top_n* chunks sorted by descending relevance score.
        Each chunk gains a 'rerank_score' key.
    """
    if not chunks:
        return []

    if len(chunks) <= top_n:
        logger.debug(
            "rerank: %d chunks ≤ top_n=%d, skipping LLM call",
            len(chunks),
            top_n,
        )
        for chunk in chunks:
            chunk.setdefault("rerank_score", 10.0)
        return chunks

    resolved_key = api_key or get_api_key()
    use_gemini = resolved_key and is_gemini_key(resolved_key)

    prompt = _build_rerank_prompt(query, chunks)
    logger.debug(
        "rerank: scoring %d chunks with %s",
        len(chunks),
        "gemini" if use_gemini else "openai",
    )

    try:
        if use_gemini:
            raw_response = _call_gemini(prompt, resolved_key)
        else:
            raw_response = _call_openai(prompt, resolved_key)

        scores = _parse_scores(raw_response, len(chunks))
        if scores is None:
            raise ValueError("Could not parse scores from LLM response")

        # Attach scores and sort
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = score

        ranked = sorted(chunks, key=lambda c: c.get("rerank_score", 0.0), reverse=True)
        top = ranked[:top_n]
        logger.info(
            "rerank: selected top %d from %d chunks (scores: %s)",
            top_n,
            len(chunks),
            [round(c.get("rerank_score", 0), 1) for c in top],
        )
        return top

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "rerank LLM call failed (%s); falling back to first %d chunks",
            exc,
            top_n,
        )
        fallback = chunks[:top_n]
        for chunk in fallback:
            chunk.setdefault("rerank_score", 0.0)
        return fallback
