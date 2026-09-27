"""
rag/sql_gen.py — Text-to-SQL Query Generator & BM25 Keyword Search
====================================================================
Provides:
  - ``bm25_search_in_database()`` — approximate BM25 keyword scoring over
    all chunks stored in the SQLite rag_document_chunks table.
  - ``generate_llm_sql_query()``  — LLM-powered natural-language → SQL
    converter using Gemini or OpenAI-compatible models.
"""

import re
import sqlite3
import logging
from typing import Any, Dict, List, Optional, Tuple

import openai
from google import genai
from google.genai import types

from backend.config import get_api_key, is_gemini_key
from backend.db import SQLITE_DB_PATH

logger = logging.getLogger("voicerag.rag.sql_gen")


# ---------------------------------------------------------------------------
# BM25 sparse keyword search
# ---------------------------------------------------------------------------

def bm25_search_in_database(
    query_text: str, top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    Approximate BM25 keyword ranking over SQLite ``rag_document_chunks``.

    Tokens shorter than 3 characters are ignored. Each matching token
    contributes ``(count * 1.8) / (count + 0.5)`` to the score.

    Args:
        query_text: Raw query string; tokenised by ``\\w+`` regex.
        top_k:      Maximum number of results to return.

    Returns:
        List of chunk dicts sorted by descending BM25 score.
    """
    tokens = [w.lower() for w in re.findall(r"\w+", query_text) if len(w) > 2]
    if not tokens:
        return []

    results: List[Dict[str, Any]] = []
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
# LLM Text-to-SQL generator
# ---------------------------------------------------------------------------

def generate_llm_sql_query(
    user_query: str,
    schemas_summary: str,
    custom_api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """
    Converts a natural-language question into a safe, read-only SQL query
    using the configured LLM.

    Args:
        user_query:      User's natural language question.
        schemas_summary: Plain-text schema description from
                         ``DatabaseManager.get_all_schemas_summary()``.
        custom_api_key:  Optional per-request API key.
        model_name:      LLM model identifier.
        provider:        ``"gemini"``, ``"groq"``, ``"ollama"``,
                         ``"openrouter"``, or ``None`` (auto-detect).
        base_url:        Custom OpenAI-compatible base URL.

    Returns:
        ``(db_id, sql_statement)`` tuple, or ``None`` if no relevant query
        could be generated.
    """
    if not schemas_summary or not user_query:
        return None

    api_key = get_api_key(custom_api_key)

    extracted_ids = re.findall(
        r"\b[A-Za-z0-9]+[-_][A-Za-z0-9]+\b|\bSTU\d+\b|\bORD\d+\b|\b\d{3,10}\b",
        user_query,
        re.IGNORECASE,
    )
    id_hint = f"EXTRACTED QUERY TARGETS: {', '.join(extracted_ids)}" if extracted_ids else ""

    prompt = (
        f"You are an expert Text-to-SQL engine for connected customer, student, and enterprise databases.\n"
        f"AVAILABLE DATABASE SCHEMAS & SAMPLE VALUES:\n{schemas_summary}\n\n"
        f"USER QUESTION: '{user_query}'\n{id_hint}\n\n"
        f"Task: Write a single valid read-only SELECT SQL query to answer the question accurately.\n"
        f"Rules:\n"
        f"1. Use column names and table names exactly as shown in the schemas.\n"
        f"2. For string matching, use case-insensitive matching e.g. LOWER(name) LIKE '%amara%' or order_id LIKE '%ORD-9021%'.\n"
        f"3. Output format MUST be exactly:\n"
        f"DB_ID: <database_id>\n"
        f"SQL: <SELECT_query>\n"
        f"If no DB table is relevant, output ONLY 'NONE'."
    )

    def _parse(text: str) -> Optional[Tuple[str, str]]:
        if not text or "NONE" in text.strip().upper():
            return None
        cleaned = re.sub(r"```(?:sql)?", "", text).replace("```", "").strip()
        db_match  = re.search(r"DB_ID:\s*([^\n\r]+)", cleaned, re.IGNORECASE)
        sql_match = re.search(r"SQL:\s*(SELECT[\s\S]+)", cleaned, re.IGNORECASE)
        if db_match and sql_match:
            db_id    = db_match.group(1).strip().strip("'\"`")
            sql_stmt = sql_match.group(2).strip().rstrip(";") + ";"
            return db_id, sql_stmt
        select_match = re.search(r"(SELECT[\s\S]+?;)", cleaned, re.IGNORECASE)
        if select_match:
            first_db_id = "customer_support_db" if "customer_support_db" in schemas_summary else "primary_db"
            return first_db_id, select_match.group(1).strip()
        return None

    try:
        is_gemini = (provider == "gemini") or (
            is_gemini_key(api_key) and not provider and not base_url
        )

        if is_gemini and not base_url:
            client = genai.Client(api_key=api_key)
            for m in ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]:
                try:
                    res = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=200),
                    )
                    if res and res.text:
                        parsed = _parse(res.text)
                        if parsed:
                            return parsed
                except Exception:
                    continue
        else:
            resolved_base_url = base_url
            if provider == "groq" and not resolved_base_url:
                resolved_base_url = "https://api.groq.com/openai/v1"
            elif provider == "ollama" and not resolved_base_url:
                resolved_base_url = "http://localhost:11434/v1"
            elif provider == "openrouter" and not resolved_base_url:
                resolved_base_url = "https://openrouter.ai/api/v1"

            client_kwargs: Dict[str, Any] = {"api_key": api_key if api_key else "ollama"}
            if resolved_base_url:
                client_kwargs["base_url"] = resolved_base_url

            client = openai.OpenAI(**client_kwargs)
            completion = client.chat.completions.create(
                model=model_name or "gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            text = completion.choices[0].message.content
            if text:
                parsed = _parse(text)
                if parsed:
                    return parsed
    except Exception as e:
        logger.debug(f"Text-to-SQL note: {e}")

    return None
