"""
rag/embedder.py — Embedding Engine
====================================
Provides get_text_embedding() for Gemini (gemini-embedding-001) and OpenAI
(text-embedding-3-small), with an in-process LRU cache to avoid redundant API
calls across the same session.

Also exposes get_embeddings_batch() for bulk ingestion pipelines.
"""

import logging
import random
from typing import Dict, List, Optional

import openai
from google import genai

from backend.config import get_api_key, is_gemini_key

logger = logging.getLogger("voicerag.rag.embedder")

# ---------------------------------------------------------------------------
# Module-level cache — shared across the process lifetime
# ---------------------------------------------------------------------------
_CACHED_EMBEDDING_MODEL: Optional[str] = "models/gemini-embedding-001"
_EMBEDDING_CACHE: Dict[str, List[float]] = {}

# Models tried in order for Gemini embedding
_GEMINI_EMBEDDING_MODELS = [
    "models/gemini-embedding-001",
    "models/gemini-embedding-2",
]


def get_text_embedding(text: str, custom_api_key: Optional[str] = None) -> List[float]:
    """
    Generates a dense embedding vector for *text* using the configured LLM
    provider (Gemini or OpenAI).

    Results are cached in ``_EMBEDDING_CACHE`` keyed by
    ``<api_key_tag>_<hash(text)>`` to avoid redundant API round-trips.

    Args:
        text:           Raw text to embed.
        custom_api_key: Optional override API key; falls back to env config.

    Returns:
        A list of floats representing the embedding vector.
        On Gemini failure a deterministic 768-dim fallback vector is returned.
    """
    global _CACHED_EMBEDDING_MODEL, _EMBEDDING_CACHE

    cleaned_text = text.replace("\n", " ").strip()
    cache_key = f"{custom_api_key or 'default'}_{hash(cleaned_text)}"

    if cache_key in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[cache_key]

    api_key = get_api_key(custom_api_key)

    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
        for m in _GEMINI_EMBEDDING_MODELS:
            try:
                res = client.models.embed_content(model=m, contents=cleaned_text)
                emb = (
                    res.embedding.values
                    if hasattr(res, "embedding") and res.embedding
                    else res.embeddings[0].values
                )
                if emb and len(emb) > 0:
                    _CACHED_EMBEDDING_MODEL = m
                    _EMBEDDING_CACHE[cache_key] = list(emb)
                    return list(emb)
            except Exception as e:
                logger.debug(f"Embedding model {m} note: {e}")
                continue

        # Deterministic fallback vector on total Gemini failure
        logger.warning("Gemini embedding calls failed. Using deterministic fallback vector.")
        rng = random.Random(hash(cleaned_text))
        fallback_emb = [rng.uniform(-0.1, 0.1) for _ in range(768)]
        _EMBEDDING_CACHE[cache_key] = fallback_emb
        return fallback_emb

    else:
        # OpenAI-compatible path (also used for Groq, OpenRouter, etc.)
        client = openai.OpenAI(api_key=api_key)
        res = client.embeddings.create(
            model="text-embedding-3-small",
            input=cleaned_text,
            encoding_format="float",
        )
        emb = res.data[0].embedding
        _EMBEDDING_CACHE[cache_key] = emb
        return emb


def get_embeddings_batch(
    texts: List[str], custom_api_key: Optional[str] = None
) -> List[List[float]]:
    """
    Embeds a list of texts in an efficient batch call where supported.

    For Gemini: falls back to sequential ``get_text_embedding()`` calls per
    text because the SDK's batch endpoint is model-dependent.
    For OpenAI: uses the native batch endpoint for efficiency.

    Args:
        texts:          List of raw text strings to embed.
        custom_api_key: Optional override API key.

    Returns:
        Ordered list of embedding vectors, one per input text.
    """
    global _CACHED_EMBEDDING_MODEL

    api_key = get_api_key(custom_api_key)
    cleaned_texts = [t.replace("\n", " ") for t in texts]

    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
        target_model = _CACHED_EMBEDDING_MODEL or "models/gemini-embedding-001"
        embeddings = []
        for t in cleaned_texts:
            try:
                res = client.models.embed_content(model=target_model, contents=t)
                emb = (
                    res.embedding.values
                    if hasattr(res, "embedding") and res.embedding
                    else res.embeddings[0].values
                )
                embeddings.append(list(emb))
            except Exception:
                embeddings.append(get_text_embedding(t, custom_api_key))
        return embeddings
    else:
        client = openai.OpenAI(api_key=api_key)
        res = client.embeddings.create(
            model="text-embedding-3-small",
            input=cleaned_texts,
            encoding_format="float",
        )
        return [item.embedding for item in res.data]
