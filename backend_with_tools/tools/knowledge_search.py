"""
Internal Knowledge Base Vector Retrieval Tool.

Performs cross-lingual hybrid (Dense Vector + BM25 Lexical) search over ingested document chunks.
"""

from typing import List, Dict, Any, Optional

from backend_with_tools.tools.base import register_tool


@register_tool(
    name="search_knowledge_base",
    description="Performs cross-lingual hybrid (Dense Vector + BM25 Lexical) search over ingested document chunks.",
)
def search_knowledge_base(
    query_text: str,
    top_k: int = 8,
    custom_api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Searches vector & keyword database using query text."""
    from backend_with_tools.rag_service import get_embedding, search_vector_database
    query_embedding = get_embedding(query_text, custom_api_key=custom_api_key)
    return search_vector_database(
        query_embedding=query_embedding,
        top_k=top_k,
        query_text=query_text,
        custom_api_key=custom_api_key,
    )
