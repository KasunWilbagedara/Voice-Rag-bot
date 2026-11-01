"""
backend/rag/__init__.py — RAG Package Public API
=================================================
Single authoritative source for the entire RAG surface.
All symbols are implemented in the sub-modules below — no imports from the
legacy ``rag_service.py`` monolith.

Sub-modules
-----------
chunker   — recursive_structural_chunk()
embedder  — get_text_embedding(), get_embeddings_batch()
retriever — search_similar_chunks()
prompts   — build_language_instruction(), build_system_prompt()
generator — call_remote_tool(), query_rag(), generate_rag_response()
ingester  — ingest_document(), save_chat_history()
sql_gen   — bm25_search_in_database(), generate_llm_sql_query()

Backward-compatible aliases
----------------------------
get_embedding             → get_text_embedding
search_vector_database    → search_similar_chunks
generate_voice_rag_answer → query_rag
"""

# --- Chunking ---
from backend.rag.chunker import recursive_structural_chunk

# --- Embedding (primary names + legacy alias) ---
from backend.rag.embedder import get_text_embedding, get_embeddings_batch
get_embedding = get_text_embedding

# --- Retrieval (primary name + legacy alias) ---
from backend.rag.retriever import search_similar_chunks
search_vector_database = search_similar_chunks

# --- Prompt builders ---
from backend.rag.prompts import build_language_instruction, build_system_prompt

# --- LLM generator + remote tool delegation ---
from backend.rag.generator import call_remote_tool, query_rag, generate_rag_response
generate_voice_rag_answer = query_rag

# --- Document ingestion & chat history ---
from backend.rag.ingester import ingest_document, save_chat_history

# --- Text-to-SQL & BM25 search ---
from backend.rag.sql_gen import bm25_search_in_database, generate_llm_sql_query

__all__ = [
    # Chunking
    "recursive_structural_chunk",
    # Embedding
    "get_text_embedding",
    "get_embedding",
    "get_embeddings_batch",
    # Retrieval
    "search_similar_chunks",
    "search_vector_database",
    # Prompts
    "build_language_instruction",
    "build_system_prompt",
    # Generator
    "call_remote_tool",
    "query_rag",
    "generate_rag_response",
    "generate_voice_rag_answer",
    # Ingestion
    "ingest_document",
    "save_chat_history",
    # SQL / BM25
    "bm25_search_in_database",
    "generate_llm_sql_query",
]
