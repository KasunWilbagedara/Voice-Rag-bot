"""
rag_v2/core/pipeline.py
-----------------------
End-to-end RAG orchestrator.

RAGPipeline wires together:
  1. Memory   – fetch/save conversation history
  2. Embedder – dense query vector
  3. Retriever – hybrid BM25 + vector search
  4. Reranker  – LLM-based relevance scoring
  5. Tool detection & execution (weather, SQL, web-search keywords)
  6. Generator – streaming or non-streaming LLM response with citations
"""

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

from rag_v2.config import get_api_key
from rag_v2.core.embedder import get_embedding
from rag_v2.core.generator import generate_answer, generate_stream
from rag_v2.core.reranker import rerank
from rag_v2.core.retriever import hybrid_search
from rag_v2.storage.memory import get_history, save_message

logger = logging.getLogger("rag_v2.core.pipeline")


# ---------------------------------------------------------------------------
# Tool detection helpers
# ---------------------------------------------------------------------------

_WEATHER_KEYWORDS = re.compile(
    r"\b(weather|temperature|forecast|rain|sunny|humidity|wind|climate)\b",
    re.IGNORECASE,
)
_SQL_KEYWORDS = re.compile(
    r"\b(how many|count|total|average|sum|list all|show me|database|table|records?)\b",
    re.IGNORECASE,
)
_SEARCH_KEYWORDS = re.compile(
    r"\b(latest|recent|news|current|today|2024|2025|search|find out|look up)\b",
    re.IGNORECASE,
)


def _detect_tools(query: str) -> List[str]:
    """Return a list of tool names required by *query*."""
    tools: List[str] = []
    if _WEATHER_KEYWORDS.search(query):
        tools.append("weather")
    if _SQL_KEYWORDS.search(query):
        tools.append("sql")
    if _SEARCH_KEYWORDS.search(query):
        tools.append("web_search")
    return tools


# ---------------------------------------------------------------------------
# Tool execution stubs
# (Replace with real integrations; these return sensible placeholder data)
# ---------------------------------------------------------------------------

async def _call_weather_tool(query: str) -> Dict[str, Any]:
    """Fetch live weather data for the location inferred from *query*."""
    # Extract a potential location from the query (naive: last capitalised word)
    words = query.split()
    location = next(
        (w for w in reversed(words) if w and w[0].isupper() and len(w) > 1),
        "your location",
    )
    logger.info("weather tool: querying for location %r", location)

    try:
        import aiohttp  # type: ignore

        async with aiohttp.ClientSession() as session:
            url = (
                f"https://wttr.in/{location}?format=j1"
            )
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    current = data.get("current_condition", [{}])[0]
                    return {
                        "tool": "weather",
                        "result": {
                            "location": location,
                            "temp_c": current.get("temp_C", "N/A"),
                            "feels_like_c": current.get("FeelsLikeC", "N/A"),
                            "description": (
                                current.get("weatherDesc", [{}])[0].get("value", "N/A")
                            ),
                            "humidity": current.get("humidity", "N/A"),
                            "wind_kmph": current.get("windspeedKmph", "N/A"),
                        },
                    }
    except Exception as exc:  # noqa: BLE001
        logger.warning("weather tool HTTP call failed: %s", exc)

    # Fallback placeholder
    return {
        "tool": "weather",
        "result": {
            "location": location,
            "note": "Live weather data unavailable; please try again later.",
        },
    }


async def _call_sql_tool(query: str) -> Dict[str, Any]:
    """
    Execute a lightweight read-only SQL query derived from *query*.

    This stub returns the row count of rag_v2_chunks as a demonstration.
    Replace with a proper NL→SQL service for production use.
    """
    logger.info("sql tool: generating query for: %r", query[:80])
    try:
        from rag_v2.storage.db import get_db_connection  # lazy import

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total_chunks FROM rag_v2_chunks"
            )
            row = cur.fetchone()
            total = row[0] if row else 0
        conn.close()
        return {
            "tool": "sql",
            "result": {
                "query": "SELECT COUNT(*) FROM rag_v2_chunks",
                "total_chunks": total,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("sql tool failed: %s", exc)
        return {"tool": "sql", "result": {"error": str(exc)}}


async def _call_web_search_tool(query: str) -> Dict[str, Any]:
    """
    Perform a lightweight web search for *query*.

    Uses DuckDuckGo's instant-answer API (no auth required).
    Replace with a richer search API (Serper, Bing, etc.) for production.
    """
    logger.info("web_search tool: searching for %r", query[:80])
    try:
        import aiohttp  # type: ignore

        async with aiohttp.ClientSession() as session:
            params = {"q": query, "format": "json", "no_html": "1"}
            async with session.get(
                "https://api.duckduckgo.com/",
                params=params,
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    abstract = data.get("AbstractText", "")
                    source = data.get("AbstractSource", "")
                    answer = data.get("Answer", "")
                    return {
                        "tool": "web_search",
                        "result": {
                            "query": query,
                            "abstract": abstract or answer or "No instant answer found.",
                            "source": source,
                        },
                    }
    except Exception as exc:  # noqa: BLE001
        logger.warning("web_search tool failed: %s", exc)

    return {
        "tool": "web_search",
        "result": {
            "query": query,
            "note": "Web search unavailable; using retrieved context only.",
        },
    }


async def _run_tools(query: str, tool_names: List[str]) -> List[Dict[str, Any]]:
    """Run all detected tools concurrently and return their results."""
    tasks = []
    for tool in tool_names:
        if tool == "weather":
            tasks.append(_call_weather_tool(query))
        elif tool == "sql":
            tasks.append(_call_sql_tool(query))
        elif tool == "web_search":
            tasks.append(_call_web_search_tool(query))

    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    tool_results: List[Dict[str, Any]] = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Tool raised an exception: %s", r)
        else:
            tool_results.append(r)
    return tool_results


# ---------------------------------------------------------------------------
# RAGPipeline
# ---------------------------------------------------------------------------

class RAGPipeline:
    """
    End-to-end RAG orchestrator.

    Usage
    -----
    ::

        pipeline = RAGPipeline(api_key="AIza...")

        # Streaming
        async for sse_chunk in pipeline.run_stream("What is the policy?"):
            print(sse_chunk, end="")

        # Non-streaming
        result = await pipeline.run("What is the policy?")
        print(result["answer"])
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key: str = api_key or get_api_key()
        logger.info(
            "RAGPipeline initialised (provider=%s)",
            "gemini" if self.api_key and self.api_key.startswith("AIza") else "openai",
        )

    # ------------------------------------------------------------------
    # Streaming entry point
    # ------------------------------------------------------------------

    async def run_stream(
        self,
        query: str,
        session_id: str = "default",
        top_k: int = 10,
        rerank_top_n: int = 4,
    ) -> AsyncGenerator[str, None]:
        """
        Run the full RAG pipeline and stream the response as SSE events.

        Parameters
        ----------
        query : str
            The user's question.
        session_id : str
            Conversation session identifier for memory isolation.
        top_k : int
            Number of chunks to retrieve before reranking.
        rerank_top_n : int
            Number of chunks to keep after reranking.

        Yields
        ------
        str
            SSE-formatted strings (``data: {...}\\n\\n``).
        """
        logger.info("run_stream: session=%s query=%r", session_id, query[:80])

        # 1. Fetch conversation history
        history = await asyncio.get_event_loop().run_in_executor(
            None, get_history, session_id
        )

        # 2. Embed the query
        query_embedding: List[float] = await asyncio.get_event_loop().run_in_executor(
            None, get_embedding, query, self.api_key, None
        )

        # 3. Hybrid retrieval
        retrieved: List[Dict[str, Any]] = await asyncio.get_event_loop().run_in_executor(
            None, hybrid_search, query, query_embedding, top_k, None
        )
        logger.debug("run_stream: retrieved %d chunks", len(retrieved))

        # 4. Rerank
        reranked: List[Dict[str, Any]] = await asyncio.get_event_loop().run_in_executor(
            None, rerank, query, retrieved, rerank_top_n, self.api_key
        )
        logger.debug("run_stream: reranked to %d chunks", len(reranked))

        # 5. Tool detection & execution
        tool_names = _detect_tools(query)
        tool_results: List[Dict[str, Any]] = []
        if tool_names:
            logger.info("run_stream: running tools: %s", tool_names)
            tool_results = await _run_tools(query, tool_names)

        # 6. Stream the response, collecting full answer text
        full_answer_parts: List[str] = []
        async for sse_chunk in generate_stream(
            query=query,
            chunks=reranked,
            history=history,
            api_key=self.api_key,
            tool_results=tool_results if tool_results else None,
        ):
            yield sse_chunk
            # Collect text fragments for memory persistence
            try:
                payload_str = sse_chunk.lstrip("data: ").rstrip("\n")
                payload = json.loads(payload_str)
                if payload.get("type") == "text":
                    full_answer_parts.append(payload.get("content", ""))
            except (json.JSONDecodeError, ValueError):
                pass

        # 7. Persist to memory
        full_answer = "".join(full_answer_parts)
        if full_answer:
            await asyncio.get_event_loop().run_in_executor(
                None, save_message, session_id, "user", query
            )
            await asyncio.get_event_loop().run_in_executor(
                None, save_message, session_id, "assistant", full_answer
            )
            logger.debug("run_stream: saved messages to memory for session %s", session_id)

    # ------------------------------------------------------------------
    # Non-streaming entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        query: str,
        session_id: str = "default",
        top_k: int = 10,
        rerank_top_n: int = 4,
    ) -> Dict[str, Any]:
        """
        Run the full RAG pipeline and return a complete response dict.

        Parameters
        ----------
        query : str
            The user's question.
        session_id : str
            Conversation session identifier.
        top_k : int
            Number of chunks to retrieve before reranking.
        rerank_top_n : int
            Number of chunks to keep after reranking.

        Returns
        -------
        Dict
            {
              "answer":       str,
              "citations":    List[Dict],
              "session_id":   str,
              "tool_results": List[Dict],
            }
        """
        logger.info("run: session=%s query=%r", session_id, query[:80])
        loop = asyncio.get_event_loop()

        # 1. Conversation history
        history = await loop.run_in_executor(None, get_history, session_id)

        # 2. Query embedding
        query_embedding: List[float] = await loop.run_in_executor(
            None, get_embedding, query, self.api_key, None
        )

        # 3. Hybrid retrieval
        retrieved: List[Dict[str, Any]] = await loop.run_in_executor(
            None, hybrid_search, query, query_embedding, top_k, None
        )
        logger.debug("run: retrieved %d chunks", len(retrieved))

        # 4. Rerank
        reranked: List[Dict[str, Any]] = await loop.run_in_executor(
            None, rerank, query, retrieved, rerank_top_n, self.api_key
        )
        logger.debug("run: reranked to %d chunks", len(reranked))

        # 5. Tool detection & execution
        tool_names = _detect_tools(query)
        tool_results: List[Dict[str, Any]] = []
        if tool_names:
            logger.info("run: running tools: %s", tool_names)
            tool_results = await _run_tools(query, tool_names)

        # 6. Generate answer (non-streaming)
        answer, citations = await loop.run_in_executor(
            None,
            generate_answer,
            query,
            reranked,
            history,
            self.api_key,
            tool_results if tool_results else None,
        )

        # 7. Persist to memory
        await loop.run_in_executor(None, save_message, session_id, "user", query)
        await loop.run_in_executor(None, save_message, session_id, "assistant", answer)
        logger.debug("run: saved messages to memory for session %s", session_id)

        logger.info(
            "run: finished session=%s answer_len=%d citations=%d",
            session_id,
            len(answer),
            len(citations),
        )
        return {
            "answer": answer,
            "citations": citations,
            "session_id": session_id,
            "tool_results": tool_results,
        }
