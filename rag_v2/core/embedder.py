"""
rag_v2/core/embedder.py
-----------------------
Dual-provider embedding engine supporting Google Gemini and OpenAI.

Features:
  - In-memory LRU cache (max 500 entries)
  - Auto provider detection from API key prefix
  - Text pre-processing (strip + 8 000 char truncation)
  - Batch embedding helper
"""

import logging
from collections import OrderedDict
from typing import Dict, List, Optional

from rag_v2.config import (
    GEMINI_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    get_api_key,
    get_provider,
    is_gemini_key,
)

logger = logging.getLogger("rag_v2.core.embedder")

# ---------------------------------------------------------------------------
# LRU cache
# ---------------------------------------------------------------------------
_CACHE_MAX = 500
_CACHE: "OrderedDict[str, List[float]]" = OrderedDict()


def _cache_get(key: str) -> Optional[List[float]]:
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    return None


def _cache_put(key: str, value: List[float]) -> None:
    if key in _CACHE:
        _CACHE.move_to_end(key)
    else:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.popitem(last=False)  # evict least-recently-used
    _CACHE[key] = value


# ---------------------------------------------------------------------------
# Internal embedding helpers
# ---------------------------------------------------------------------------

def _embed_gemini(text: str, api_key: str) -> List[float]:
    """Embed *text* using the Google Gemini embedding API."""
    try:
        from google import genai  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "google-generativeai is required for Gemini embeddings. "
            "Install it with: pip install google-generativeai"
        ) from exc

    client = genai.Client(api_key=api_key)
    response = client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=text,
    )
    # The SDK returns an EmbedContentResponse; access the values list
    embedding = response.embeddings[0].values
    logger.debug("Gemini embedding: %d dims", len(embedding))
    return list(embedding)


def _embed_openai(text: str, api_key: str) -> List[float]:
    """Embed *text* using the OpenAI embedding API."""
    try:
        import openai  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "openai is required for OpenAI embeddings. "
            "Install it with: pip install openai"
        ) from exc

    client = openai.OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=text,
    )
    embedding = response.data[0].embedding
    logger.debug("OpenAI embedding: %d dims", len(embedding))
    return list(embedding)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_embedding(
    text: str,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
) -> List[float]:
    """
    Generate a dense embedding vector for *text*.

    Provider resolution order:
      1. Explicit *provider* argument ('gemini' | 'openai')
      2. Auto-detected from *api_key* prefix ('AIza…' → gemini, 'sk-…' → openai)
      3. Defaults from rag_v2.config (get_provider / get_api_key)

    Parameters
    ----------
    text : str
        The text to embed.
    api_key : str, optional
        API key; falls back to config if omitted.
    provider : str, optional
        'gemini' or 'openai'; auto-detected if omitted.

    Returns
    -------
    List[float]
        Embedding vector (768-dim for Gemini, 1536-dim for OpenAI).
    """
    # Resolve API key
    resolved_key = api_key or get_api_key()

    # Resolve provider
    if provider is None:
        if resolved_key and is_gemini_key(resolved_key):
            resolved_provider = "gemini"
        elif resolved_key and resolved_key.startswith("sk-"):
            resolved_provider = "openai"
        else:
            resolved_provider = get_provider()
    else:
        resolved_provider = provider.lower()

    # Pre-process text
    cleaned = text.strip()[:8000]
    if not cleaned:
        logger.warning("get_embedding called with empty text; returning zero vector")
        dim = 768 if resolved_provider == "gemini" else 1536
        return [0.0] * dim

    # Cache lookup
    cache_key = f"{cleaned[:100]}|{resolved_provider}"
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache hit for embedding (provider=%s)", resolved_provider)
        return cached

    # Generate embedding
    logger.debug("Generating %s embedding for %d-char text", resolved_provider, len(cleaned))
    if resolved_provider == "gemini":
        vector = _embed_gemini(cleaned, resolved_key)
    elif resolved_provider == "openai":
        vector = _embed_openai(cleaned, resolved_key)
    else:
        raise ValueError(
            f"Unknown provider '{resolved_provider}'. Must be 'gemini' or 'openai'."
        )

    _cache_put(cache_key, vector)
    return vector


def get_embeddings_batch(
    texts: List[str],
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
) -> List[List[float]]:
    """
    Generate embeddings for a list of texts.

    This is a sequential wrapper around :func:`get_embedding`.  Results are
    returned in the same order as *texts*.

    Parameters
    ----------
    texts : List[str]
        Texts to embed.
    api_key : str, optional
        API key passed through to :func:`get_embedding`.
    provider : str, optional
        Provider override passed through to :func:`get_embedding`.

    Returns
    -------
    List[List[float]]
        List of embedding vectors, one per input text.
    """
    logger.info("Batch embedding %d texts", len(texts))
    results: List[List[float]] = []
    for idx, text in enumerate(texts):
        try:
            vec = get_embedding(text, api_key=api_key, provider=provider)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to embed text[%d]: %s", idx, exc)
            raise
        results.append(vec)
    return results
