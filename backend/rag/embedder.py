"""
rag/embedder.py — Embedding Engine
====================================
One embedding model per provider, always EMBEDDING_DIM (768) dimensions:

  Gemini key → gemini-embedding-001  (asked for 768 dims)
  OpenAI key → text-embedding-3-small (asked for 768 dims)

A fixed size lets PostgreSQL store embeddings in a vector(768) column with an
HNSW index. Vectors from different models are not comparable, so every stored
chunk also records which model produced it (see embedding_model_name()).
"""

import logging
from typing import Dict, List, Optional

import openai
from google import genai
from google.genai import types

from backend.config import get_api_key, is_gemini_key

logger = logging.getLogger("voicerag.rag.embedder")

EMBEDDING_DIM = 768
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 100  # max texts per embedding API call

_EMBEDDING_CACHE: Dict[str, List[float]] = {}


def embedding_model_name(custom_api_key: Optional[str] = None) -> str:
    """Name of the embedding model used for the active API key."""
    api_key = get_api_key(custom_api_key)
    return GEMINI_EMBEDDING_MODEL if is_gemini_key(api_key) else OPENAI_EMBEDDING_MODEL


def get_embeddings_batch(texts: List[str], custom_api_key: Optional[str] = None) -> List[List[float]]:
    """Embeds *texts* (in order). Raises on API errors — never returns fake vectors."""
    api_key = get_api_key(custom_api_key)
    cleaned = [t.replace("\n", " ").strip() for t in texts]
    vectors: List[List[float]] = []

    for start in range(0, len(cleaned), _BATCH_SIZE):
        batch = cleaned[start:start + _BATCH_SIZE]
        if is_gemini_key(api_key):
            client = genai.Client(api_key=api_key)
            res = client.models.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )
            vectors.extend(list(e.values) for e in res.embeddings)
        else:
            client = openai.OpenAI(api_key=api_key)
            res = client.embeddings.create(
                model=OPENAI_EMBEDDING_MODEL,
                input=batch,
                dimensions=EMBEDDING_DIM,
                encoding_format="float",
            )
            vectors.extend(item.embedding for item in res.data)

    return vectors


def get_text_embedding(text: str, custom_api_key: Optional[str] = None) -> List[float]:
    """Embeds one text, with an in-process cache."""
    cache_key = f"{embedding_model_name(custom_api_key)}|{text.strip()}"
    if cache_key not in _EMBEDDING_CACHE:
        if len(_EMBEDDING_CACHE) > 2000:
            _EMBEDDING_CACHE.clear()  # keep memory bounded
        _EMBEDDING_CACHE[cache_key] = get_embeddings_batch([text], custom_api_key)[0]
    return _EMBEDDING_CACHE[cache_key]
