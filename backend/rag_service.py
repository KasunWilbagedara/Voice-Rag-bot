import uuid
import re
import json
import math
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import openai
from google import genai
from google.genai import types

from backend.config import get_api_key, is_gemini_key
from backend.db import (
    get_db_connection,
    is_db_connected,
    in_memory_store,
    cosine_similarity,
)
from backend import db_query_service

logger = logging.getLogger("voicerag.rag_service")

# Global cached embedding model name
_CACHED_EMBEDDING_MODEL: Optional[str] = None


# --- 1. RECURSIVE STRUCTURAL CHUNKING ---
def recursive_structural_chunk(
    text: str,
    target_size: int = 450,
    overlap: int = 80,
) -> List[str]:
    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    sections = re.split(r"(?=\n#{1,3}\s+|\n--- Page \d+ ---\n|\n### Slide \d+)", cleaned)
    chunks: List[str] = []

    for section in sections:
        sec_text = section.strip()
        if not sec_text:
            continue

        if len(sec_text) <= target_size + overlap:
            if len(sec_text) > 10:
                chunks.append(sec_text)
        else:
            paragraphs = sec_text.split("\n\n")
            current_chunk = ""

            for para in paragraphs:
                para_clean = para.strip()
                if not para_clean:
                    continue

                if len(current_chunk) + len(para_clean) + 2 <= target_size:
                    current_chunk += ("\n\n" if current_chunk else "") + para_clean
                else:
                    if current_chunk and len(current_chunk) > 10:
                        chunks.append(current_chunk.strip())

                    if len(para_clean) > target_size:
                        sentences = re.split(r"(?<=[.!?;])\s+", para_clean)
                        sub_chunk = ""
                        for sent in sentences:
                            if len(sub_chunk) + len(sent) + 1 <= target_size:
                                sub_chunk += (" " if sub_chunk else "") + sent
                            else:
                                if sub_chunk and len(sub_chunk) > 10:
                                    chunks.append(sub_chunk.strip())
                                sub_chunk = sent
                        if sub_chunk and len(sub_chunk) > 10:
                            chunks.append(sub_chunk.strip())
                        current_chunk = ""
                    else:
                        current_chunk = para_clean

            if current_chunk and len(current_chunk) > 10:
                chunks.append(current_chunk.strip())

    return chunks if chunks else [cleaned[:target_size]]


# --- 2. CROSS-LINGUAL QUERY TRANSLATION (Sinhala -> English for Search) ---
def translate_query_for_search(
    query_text: str,
    custom_api_key: Optional[str] = None,
) -> str:
    """If user asks in Sinhala, generates a fast English translation to match English documents."""
    if not query_text or not any("\u0d80" <= c <= "\u0dff" for c in query_text):
        return query_text

    try:
        api_key = get_api_key(custom_api_key)
        if is_gemini_key(api_key):
            client = genai.Client(api_key=api_key)
            prompt = f"Translate this Sinhala user question into a concise English document search query: '{query_text}'. Output ONLY the English search string."
            for m_name in ["gemini-flash-latest", "gemini-2.0-flash", "gemini-3.6-flash"]:
                try:
                    res = client.models.generate_content(
                        model=m_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(max_output_tokens=60, temperature=0.1)
                    )
                    if res and res.text and res.text.strip():
                        return res.text.strip()
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"Query translation fallback: {e}")

    return query_text


# --- 4. DOCUMENT INGESTION ---
def ingest_document(
    title: str,
    file_type: str,
    content: str,
    custom_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    raw_chunks = recursive_structural_chunk(content)
    if not raw_chunks:
        raise ValueError("Document content is empty or contains no parseable text.")

    embeddings = get_embeddings_batch(raw_chunks, custom_api_key)
    doc_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"

    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO documents (id, title, file_type, created_at) VALUES (%s, %s, %s, %s)",
                        (doc_id, title, file_type, created_at),
                    )
                    for i, (chunk, emb) in enumerate(zip(raw_chunks, embeddings)):
                        chunk_id = str(uuid.uuid4())
                        vector_str = f"[{','.join(map(str, emb))}]"
                        cur.execute(
                            """INSERT INTO document_chunks (id, document_id, content, chunk_index, embedding, created_at)
                               VALUES (%s, %s, %s, %s, %s::vector, %s)""",
                            (chunk_id, doc_id, chunk, i, vector_str, created_at),
                        )
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Error ingesting document into DB: {e}")
                raise e
        else:
            in_memory_store.documents.append({
                "id": doc_id,
                "title": title,
                "file_type": file_type,
                "created_at": created_at,
            })
            for i, (chunk, emb) in enumerate(zip(raw_chunks, embeddings)):
                in_memory_store.chunks.append({
                    "id": str(uuid.uuid4()),
                    "document_id": doc_id,
                    "content": chunk,
                    "chunk_index": i,
                    "embedding": emb,
                    "created_at": created_at,
                })

    return {
        "documentId": doc_id,
        "title": title,
        "chunkCount": len(raw_chunks),
        "totalCharacters": len(content),
    }


# --- 5. BM25 SPARSE KEYWORD SEARCH ---
def bm25_search_in_memory(query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
    chunks = in_memory_store.chunks
    if not chunks:
        return []

    tokens = [w.lower() for w in re.findall(r"\w+", query_text) if len(w) > 2]
    if not tokens:
        return []

    scored_chunks = []
    for chunk in chunks:
        content_lower = chunk["content"].lower()
        score = 0.0
        for token in tokens:
            count = content_lower.count(token)
            if count > 0:
                score += (count * 1.5) / (count + 0.5)

        if score > 0:
            doc = next((d for d in in_memory_store.documents if d["id"] == chunk["document_id"]), None)
            scored_chunks.append({
                "id": chunk["id"],
                "documentId": chunk["document_id"],
                "documentTitle": doc["title"] if doc else "Document",
                "content": chunk["content"],
                "chunkIndex": chunk["chunk_index"],
                "score": score,
            })

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    return scored_chunks[:top_k]


# --- 6. ADVANCED CROSS-LINGUAL HYBRID RRF SEARCH ENGINE ---
def search_vector_database(
    query_embedding: List[float],
    top_k: int = 8,
    query_text: Optional[str] = None,
    custom_api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query_str = query_text or ""
    lower_query = query_str.lower()

    translated_search_str = translate_query_for_search(query_str, custom_api_key)
    search_embedding = query_embedding
    if translated_search_str and translated_search_str != query_str:
        try:
            search_embedding = get_embedding(translated_search_str, custom_api_key)
        except Exception:
            pass

    is_general_query = not query_str or any(
        kw in lower_query or kw in translated_search_str.lower()
        for kw in [
            "මොනාද", "මොනවාද", "තියෙන්නේ", "විස්තර", "ලියා", "ලේඛන", "ඩොකියුමන්ට්", "කේස්",
            "what", "summary", "overview", "about", "cv", "resume", "pdf", "case", "study", "slide"
        ]
    )

    dense_results: List[Dict[str, Any]] = []
    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    vector_str = f"[{','.join(map(str, search_embedding))}]"
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

                    if is_general_query:
                        overview_query = """
                            SELECT c.id, c.document_id, d.title AS document_title, c.content, c.chunk_index, 0.9 AS similarity
                            FROM document_chunks c
                            JOIN documents d ON c.document_id = d.id
                            WHERE c.chunk_index <= 3
                            LIMIT 6;
                        """
                        cur.execute(overview_query)
                        ov_rows = cur.fetchall()
                        for row in ov_rows:
                            if not any(r["id"] == str(row[0]) for r in dense_results):
                                dense_results.append({
                                    "id": str(row[0]),
                                    "documentId": str(row[1]),
                                    "documentTitle": row[2],
                                    "content": row[3],
                                    "chunkIndex": row[4],
                                    "similarity": 0.9,
                                })
            except Exception as e:
                logger.error(f"Error during vector search: {e}")
        else:
            scored = []
            for chunk in in_memory_store.chunks:
                doc = next((d for d in in_memory_store.documents if d["id"] == chunk["document_id"]), None)
                sim = cosine_similarity(search_embedding, chunk["embedding"])
                scored.append({
                    "id": chunk["id"],
                    "documentId": chunk["document_id"],
                    "documentTitle": doc["title"] if doc else "Document",
                    "content": chunk["content"],
                    "chunkIndex": chunk["chunk_index"],
                    "similarity": sim,
                })
            scored.sort(key=lambda x: x["similarity"], reverse=True)
            dense_results = scored[: top_k * 2]

            if is_general_query or len(dense_results) < top_k:
                overview_chunks = [c for c in in_memory_store.chunks if c["chunk_index"] <= 3]
                for chunk in overview_chunks:
                    if not any(r["id"] == chunk["id"] for r in dense_results):
                        doc = next((d for d in in_memory_store.documents if d["id"] == chunk["document_id"]), None)
                        dense_results.append({
                            "id": chunk["id"],
                            "documentId": chunk["document_id"],
                            "documentTitle": doc["title"] if doc else "Document",
                            "content": chunk["content"],
                            "chunkIndex": chunk["chunk_index"],
                            "similarity": 0.88,
                        })

    bm25_results_1 = bm25_search_in_memory(query_str, top_k=top_k)
    bm25_results_2 = bm25_search_in_memory(translated_search_str, top_k=top_k)
    bm25_results = bm25_results_1 + [b for b in bm25_results_2 if not any(x["id"] == b["id"] for x in bm25_results_1)]

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


# Global cached embedding model & LRU caches
_CACHED_EMBEDDING_MODEL: Optional[str] = None
_EMBEDDING_CACHE: Dict[str, List[float]] = {}


# --- 1. RECURSIVE STRUCTURAL CHUNKING ---
def recursive_structural_chunk(
    text: str,
    target_size: int = 450,
    overlap: int = 80,
) -> List[str]:
    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    sections = re.split(r"(?=\n#{1,3}\s+|\n--- Page \d+ ---\n|\n### Slide \d+)", cleaned)
    chunks: List[str] = []

    for section in sections:
        sec_text = section.strip()
        if not sec_text:
            continue

        if len(sec_text) <= target_size + overlap:
            if len(sec_text) > 10:
                chunks.append(sec_text)
        else:
            paragraphs = sec_text.split("\n\n")
            current_chunk = ""

            for para in paragraphs:
                para_clean = para.strip()
                if not para_clean:
                    continue

                if len(current_chunk) + len(para_clean) + 2 <= target_size:
                    current_chunk += ("\n\n" if current_chunk else "") + para_clean
                else:
                    if current_chunk and len(current_chunk) > 10:
                        chunks.append(current_chunk.strip())

                    if len(para_clean) > target_size:
                        sentences = re.split(r"(?<=[.!?;])\s+", para_clean)
                        sub_chunk = ""
                        for sent in sentences:
                            if len(sub_chunk) + len(sent) + 1 <= target_size:
                                sub_chunk += (" " if sub_chunk else "") + sent
                            else:
                                if sub_chunk and len(sub_chunk) > 10:
                                    chunks.append(sub_chunk.strip())
                                sub_chunk = sent
                        if sub_chunk and len(sub_chunk) > 10:
                            chunks.append(sub_chunk.strip())
                        current_chunk = ""
                    else:
                        current_chunk = para_clean

            if current_chunk and len(current_chunk) > 10:
                chunks.append(current_chunk.strip())

    return chunks if chunks else [cleaned[:target_size]]


# --- 2. CROSS-LINGUAL QUERY TRANSLATION (Sinhala -> English for Search) ---
def translate_query_for_search(
    query_text: str,
    custom_api_key: Optional[str] = None,
) -> str:
    """If user asks in Sinhala, generates a fast English translation to match English documents."""
    if not query_text or not any("\u0d80" <= c <= "\u0dff" for c in query_text):
        return query_text

    try:
        api_key = get_api_key(custom_api_key)
        if is_gemini_key(api_key):
            client = genai.Client(api_key=api_key)
            prompt = f"Translate this Sinhala user question into a concise English document search query: '{query_text}'. Output ONLY the English search string."
            for m_name in ["gemini-flash-latest", "gemini-2.0-flash", "gemini-3.6-flash"]:
                try:
                    res = client.models.generate_content(
                        model=m_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(max_output_tokens=60, temperature=0.1)
                    )
                    if res and res.text and res.text.strip():
                        return res.text.strip()
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"Query translation fallback: {e}")

    return query_text


# --- 3. FAST EMBEDDING ENGINE WITH LRU CACHING ---
def get_embedding(text: str, custom_api_key: Optional[str] = None) -> List[float]:
    global _CACHED_EMBEDDING_MODEL, _EMBEDDING_CACHE
    cleaned_text = text.replace("\n", " ").strip()
    cache_key = f"{custom_api_key or 'default'}_{hash(cleaned_text)}"

    if cache_key in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[cache_key]

    api_key = get_api_key(custom_api_key)

    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
        if _CACHED_EMBEDDING_MODEL:
            try:
                res = client.models.embed_content(model=_CACHED_EMBEDDING_MODEL, contents=cleaned_text)
                emb = res.embedding.values if hasattr(res, "embedding") and res.embedding else res.embeddings[0].values
                _EMBEDDING_CACHE[cache_key] = emb
                return emb
            except Exception:
                pass

        models_to_try = [
            "gemini-embedding-001",
            "gemini-embedding-2",
            "models/gemini-embedding-001",
            "models/gemini-embedding-2",
        ]
        for m in models_to_try:
            try:
                res = client.models.embed_content(model=m, contents=cleaned_text)
                _CACHED_EMBEDDING_MODEL = m
                emb = res.embedding.values if hasattr(res, "embedding") and res.embedding else res.embeddings[0].values
                _EMBEDDING_CACHE[cache_key] = emb
                return emb
            except Exception:
                continue

        logger.warning("Gemini embedding API calls failed. Using deterministic fallback vector.")
        import random
        rng = random.Random(hash(cleaned_text))
        fallback_emb = [rng.uniform(-0.1, 0.1) for _ in range(768)]
        _EMBEDDING_CACHE[cache_key] = fallback_emb
        return fallback_emb
    else:
        client = openai.OpenAI(api_key=api_key)
        res = client.embeddings.create(
            model="text-embedding-3-small",
            input=cleaned_text,
            encoding_format="float",
        )
        emb = res.data[0].embedding
        _EMBEDDING_CACHE[cache_key] = emb
        return emb


def get_embeddings_batch(texts: List[str], custom_api_key: Optional[str] = None) -> List[List[float]]:
    global _CACHED_EMBEDDING_MODEL
    api_key = get_api_key(custom_api_key)
    cleaned_texts = [t.replace("\n", " ") for t in texts]

    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
        target_model = _CACHED_EMBEDDING_MODEL or "gemini-embedding-001"
        embeddings = []
        for t in cleaned_texts:
            try:
                res = client.models.embed_content(model=target_model, contents=t)
                emb = res.embedding.values if hasattr(res, "embedding") and res.embedding else res.embeddings[0].values
                embeddings.append(emb)
            except Exception:
                embeddings.append(get_embedding(t, custom_api_key))
        return embeddings
    else:
        client = openai.OpenAI(api_key=api_key)
        res = client.embeddings.create(
            model="text-embedding-3-small",
            input=cleaned_texts,
            encoding_format="float",
        )
        return [item.embedding for item in res.data]


# --- 4. DYNAMIC LLM TEXT-TO-SQL GENERATOR ---
def generate_llm_sql_query(
    user_query: str,
    schemas_summary: str,
    custom_api_key: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """Uses LLM to convert user natural language questions into safe read-only SQL queries."""
    if not schemas_summary or not user_query:
        return None

    api_key = get_api_key(custom_api_key)

    # Extract any alphanumeric IDs (e.g. ORD-9021, CUST-1001, STU1042)
    extracted_ids = re.findall(r"\b[A-Za-z0-9]+[-_][A-Za-z0-9]+\b|\bSTU\d+\b|\bORD\d+\b", user_query, re.IGNORECASE)
    id_hint = f"EXTRACTED QUERY IDS: {', '.join(extracted_ids)}" if extracted_ids else ""

    prompt = (
        f"You are an expert Text-to-SQL engine for connected customer & enterprise databases.\n"
        f"AVAILABLE DATABASE SCHEMAS & SAMPLE VALUES:\n{schemas_summary}\n\n"
        f"USER QUESTION: '{user_query}'\n{id_hint}\n\n"
        f"Task: Write a single valid read-only SELECT SQL query to answer the question accurately.\n"
        f"Rules:\n"
        f"1. Use column names and table names exactly as shown in the schemas.\n"
        f"2. For analytical or comparative questions (e.g. 'who earns more male or female', 'average gpa by department', 'top spending customers'), write aggregate SQL queries using COUNT(*), AVG(), SUM(), GROUP BY, and ORDER BY DESC.\n"
        f"3. For text or ID searches, use wildcard matching e.g. WHERE order_id LIKE '%ORD-9021%' or LOWER(name) LIKE '%amara%'.\n"
        f"4. Output format MUST be:\n"
        f"DB_ID: <database_id>\n"
        f"SQL: <SELECT_query>\n"
        f"If no DB table is relevant, output ONLY 'NONE'."
    )

    def parse_sql_output(text: str) -> Optional[Tuple[str, str]]:
        if not text or "NONE" in text.strip().upper():
            return None

        # Strip markdown code blocks if any
        cleaned = re.sub(r"```(?:sql)?", "", text).replace("```", "").strip()

        db_match = re.search(r"DB_ID:\s*([^\n\r]+)", cleaned, re.IGNORECASE)
        sql_match = re.search(r"SQL:\s*(SELECT[\s\S]+)", cleaned, re.IGNORECASE)

        if db_match and sql_match:
            db_id = db_match.group(1).strip().strip("'\"`")
            sql_stmt = sql_match.group(2).strip().rstrip(";") + ";"
            return db_id, sql_stmt

        # Fallback regex search for any SELECT statement
        select_match = re.search(r"(SELECT[\s\S]+?;)", cleaned, re.IGNORECASE)
        if select_match:
            first_db_id = "customer_support_db" if "customer_support_db" in schemas_summary else "primary_db"
            return first_db_id, select_match.group(1).strip()

        return None

    try:
        if is_gemini_key(api_key):
            client = genai.Client(api_key=api_key)
            for m in ["gemini-flash-latest", "gemini-2.0-flash"]:
                try:
                    res = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=250)
                    )
                    if res and res.text:
                        parsed = parse_sql_output(res.text)
                        if parsed:
                            return parsed
                except Exception:
                    continue
        else:
            client = openai.OpenAI(api_key=api_key)
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=250,
            )
            text = completion.choices[0].message.content
            if text:
                parsed = parse_sql_output(text)
                if parsed:
                    return parsed
    except Exception as e:
        logger.debug(f"LLM Text-to-SQL generation note: {e}")

    return None


# --- 5. HIGH-INTELLIGENCE LLM GENERATOR & MULTI-SOURCE FUSION ---
def generate_voice_rag_answer(
    user_query: str,
    retrieved_chunks: List[Dict[str, Any]],
    custom_api_key: Optional[str] = None,
    model_name: str = "gemini-flash-latest",
    target_language: str = "si",
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Synthesizes a response by fusing unstructured vector document RAG chunks, 
    dynamic LLM Text-to-SQL query results, and multi-turn chat history.
    """
    api_key = get_api_key(custom_api_key)
    is_sinhala = target_language == "si"
    db_context_blocks = []
    enriched_chunks = list(retrieved_chunks)

    # 1. Legacy Student Database Match
    student_record = db_query_service.query_student_by_id_or_name(user_query)
    if student_record:
        db_context_blocks.append(
            f"STRUCTURED STUDENT DATABASE RECORD:\n"
            f"- Student ID: {student_record.get('student_id')}\n"
            f"- Full Name: {student_record.get('name')}\n"
            f"- Email: {student_record.get('email')}\n"
            f"- Department: {student_record.get('department')}\n"
            f"- GPA: {student_record.get('gpa')}\n"
            f"- Academic Status: {student_record.get('status')}\n"
        )
        enriched_chunks.append({
            "id": f"db_student_{student_record.get('student_id')}",
            "documentId": "database_students",
            "documentTitle": f"Database: Student ({student_record.get('student_id')})",
            "content": f"Student Record: {student_record.get('name')} | ID: {student_record.get('student_id')} | Dept: {student_record.get('department')} | GPA: {student_record.get('gpa')}",
            "chunkIndex": 0,
            "similarity": 1.0,
            "type": "database_record"
        })

    # 2. Dynamic LLM Text-to-SQL + Heuristic Auto Query Execution
    try:
        schemas_summary = db_query_service.db_manager.get_all_schemas_summary()
        
        # Try AI Text-to-SQL Generation first
        llm_sql_pair = generate_llm_sql_query(user_query, schemas_summary, custom_api_key)
        if llm_sql_pair:
            target_db, generated_sql = llm_sql_pair
            sql_res = db_query_service.db_manager.execute_safe_sql(generated_sql, db_id=target_db)
            if sql_res and sql_res.get("rows"):
                rows_data = sql_res["rows"]
                db_context_blocks.append(
                    f"AI TEXT-TO-SQL RESULT (Target DB: '{target_db}', SQL: '{generated_sql}'):\n"
                    + json.dumps(rows_data[:5], indent=2)
                )
                enriched_chunks.append({
                    "id": f"db_ai_sql_{target_db}",
                    "documentId": f"db_{target_db}",
                    "documentTitle": f"AI Text-to-SQL: {target_db}",
                    "content": f"Executed SQL: {generated_sql}\nRetrieved Rows:\n" + json.dumps(rows_data[:4]),
                    "chunkIndex": 0,
                    "similarity": 1.0,
                    "type": "database_sql"
                })

        # Heuristic fallback for active databases if AI query returned empty or failed
        if not db_context_blocks:
            all_dbs = db_query_service.db_manager.list_databases()
            query_lower = user_query.lower()

            for db in all_dbs:
                db_id = db["id"]
                schemas = db_query_service.db_manager.get_database_schema(db_id)
                for schema in schemas:
                    table_name = schema["table_name"]
                    if table_name in ["documents", "document_chunks", "chat_history"]:
                        continue

                    # Check if table name or any column name is mentioned in user query
                    col_names = [c["column"].lower() for c in schema["columns"]]
                    is_table_match = (table_name.lower() in query_lower) or any(col in query_lower for col in col_names if len(col) >= 4)

                    sql_stmt = None
                    if is_table_match:
                        sql_stmt = f"SELECT * FROM {table_name} LIMIT 10;"
                    else:
                        for word in user_query.split():
                            word_clean = word.strip(",.'\"!?")
                            if len(word_clean) >= 3 and (re.match(r"^[A-Za-z0-9]+[-_][A-Za-z0-9]+$", word_clean) or word_clean.isdigit()):
                                text_cols = [c["column"] for c in schema["columns"] if "CHAR" in c["type"].upper() or "TEXT" in c["type"].upper() or "VARCHAR" in c["type"].upper()]
                                if text_cols:
                                    clauses = [f"LOWER({col}) LIKE LOWER('%{word_clean}%')" for col in text_cols[:4]]
                                    sql_stmt = f"SELECT * FROM {table_name} WHERE {' OR '.join(clauses)} LIMIT 5;"
                                    break

                    if not sql_stmt and any(kw in query_lower for kw in ["all", "list", "show", "customer", "order", "ticket", "faq", "price", "status", "salary", "income", "data"]):
                        sql_stmt = f"SELECT * FROM {table_name} LIMIT 10;"

                    if sql_stmt:
                        sql_res = db_query_service.db_manager.execute_safe_sql(sql_stmt, db_id=db_id)
                        if sql_res and sql_res.get("rows"):
                            rows_data = sql_res["rows"]
                            db_context_blocks.append(
                                f"DATABASE '{db['name']}' -> TABLE '{table_name}' (Executed SQL: {sql_stmt}):\n"
                                + json.dumps(rows_data[:5], indent=2)
                            )
                            enriched_chunks.append({
                                "id": f"db_sql_{db_id}_{table_name}",
                                "documentId": f"db_{db_id}",
                                "documentTitle": f"Database: {db['name']} ({table_name})",
                                "content": f"SQL Query: {sql_stmt}\nResult Rows:\n" + json.dumps(rows_data[:5]),
                                "chunkIndex": 0,
                                "similarity": 0.95,
                                "type": "database_sql"
                            })
    except Exception as db_err:
        logger.warning(f"Multi-DB SQL Query execution note: {db_err}")

    # Build context string
    db_context_str = "\n\n".join(db_context_blocks) if db_context_blocks else "No specific database table match."

    # Process Multi-Turn Conversation History Context
    history_str = "None"
    if conversation_history:
        recent_turns = conversation_history[-4:]
        history_lines = [f"{turn.get('role', 'user').upper()}: {turn.get('content', '')}" for turn in recent_turns]
        history_str = "\n".join(history_lines)

    if retrieved_chunks:
        doc_context_text = "\n\n".join([
            f"--- DOCUMENT CHUNK {idx + 1} ({chunk.get('documentTitle', 'Doc')}) ---\n{chunk.get('content', '')}"
            for idx, chunk in enumerate(retrieved_chunks[:8])
        ])
    else:
        doc_context_text = "No document chunks retrieved."

    if is_sinhala:
        language_instruction = (
            "CRITICAL SINHALA VOICE & ACCURACY REQUIREMENT:\n"
            "You MUST synthesize a comprehensive, smart, and highly articulate answer in natural, fluent SINHALA (සිංහල).\n"
            "Thoroughly analyze BOTH the STRUCTURED DATABASE RECORDS and CONTEXT DOCUMENTS provided below. Explain customer facts, order statuses, policy answers, or student details clearly in Sinhala.\n\n"
            "RULES FOR SINHALA RESPONSE:\n"
            "1. Deliver a COMPLETE 3 to 6 sentence spoken response. NEVER leave your sentence incomplete or cut off!\n"
            "2. If database customer/order/ticket/student facts are provided below, explicitly state the ID, name, status, and details in natural spoken Sinhala.\n"
            "3. Take into account PREVIOUS CONVERSATION HISTORY for follow-up questions.\n"
            "4. Do NOT use markdown symbols (*, #, -), no bullet points, and no citations like [1] or [Source 1] in spoken text.\n"
            "5. COMPARATIVE, STATISTICAL & CHART DATA RULE:\n"
            "If the user asks for comparative data, statistics, figures, tabular comparisons, or numerical data, you MUST provide the spoken answer AND append a hidden JSON schema representing the data at the very end of your response inside a markdown code block ```json ... ```.\n"
            "The JSON schema MUST follow this exact structure:\n"
            "```json\n"
            "{\n"
            '  "type": "chart",\n'
            '  "chartType": "bar",\n'
            '  "title": "Chart Title",\n'
            '  "labels": ["Label 1", "Label 2"],\n'
            '  "datasets": [\n'
            "    {\n"
            '      "label": "Dataset Name",\n'
            '      "data": [100, 200]\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "```\n"
            "Use 'bar' for entity comparisons, 'pie' for proportions, and 'line' for trends. If NOT comparative data, do NOT output JSON."
        )
    else:
        language_instruction = (
            "CRITICAL VOICE & ACCURACY REQUIREMENT:\n"
            "Deliver an intelligent, comprehensive, and highly accurate answer grounded strictly in the STRUCTURED DATABASE RECORDS and CONTEXT DOCUMENTS below.\n\n"
            "RULES FOR RESPONSE:\n"
            "1. Synthesize a COMPLETE 3 to 6 sentence spoken response.\n"
            "2. If customer, order, ticket, or student database records are provided, state key facts (IDs, amounts, statuses, names) clearly.\n"
            "3. Consider PREVIOUS CONVERSATION HISTORY for contextual follow-up questions.\n"
            "4. Do NOT use markdown symbols (*, #, -), no bullet points, and no citations.\n"
            "5. COMPARATIVE, STATISTICAL & CHART DATA RULE:\n"
            "If comparing numbers or statistical data, append a hidden JSON schema representing the data at the end inside ```json ... ```."
        )

    system_prompt = (
        f"You are an exceptionally smart, articulate, and accurate Customer Support AI Voice Assistant powering an enterprise Multi-DB & Multi-Doc Voice-RAG system.\n\n"
        f"{language_instruction}\n\n"
        f"PREVIOUS CONVERSATION HISTORY:\n{history_str}\n\n"
        f"CONNECTED STRUCTURED DATABASE Context:\n{db_context_str}\n\n"
        f"UNSTRUCTURED CONTEXT DOCUMENTS:\n{doc_context_text}"
    )

    generated_text = ""
    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
        full_prompt = f"{system_prompt}\n\nUSER QUESTION: {user_query}"

        models_to_try = [
            "gemini-flash-latest",
            "gemini-2.0-flash",
            "gemini-3.6-flash",
            "gemini-pro-latest",
            "gemini-3.5-flash",
        ]
        last_err = None

        for m_name in models_to_try:
            try:
                res = client.models.generate_content(
                    model=m_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=1200,
                    ),
                )
                if res and res.text and res.text.strip():
                    generated_text = res.text.strip()
                    break
            except Exception as e:
                last_err = e

        if not generated_text:
            raise RuntimeError(f"Gemini LLM generation failed: {last_err}")
    else:
        client = openai.OpenAI(api_key=api_key)
        active_model = model_name if "gpt" in model_name else "gpt-4o-mini"
        completion = client.chat.completions.create(
            model=active_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        ans = completion.choices[0].message.content
        generated_text = ans.strip() if ans else ("පිළිතුරක් සෑදීමට නොහැකි විය." if is_sinhala else "I could not generate a response.")

    # Strip any internal LLM scratchpad / reasoning lines e.g. "thought Let's check row..."
    if generated_text:
        clean_lines = []
        for line in generated_text.splitlines():
            l_strip = line.strip()
            if l_strip.lower().startswith(("thought ", "thought:", "thinking:", "reasoning:")):
                continue
            clean_lines.append(line)
        generated_text = "\n".join(clean_lines).strip()

    return {
        "answer": generated_text,
        "retrievedChunks": enriched_chunks,
    }


def save_chat_history(
    user_query_text: str,
    retrieved_chunks: List[Dict[str, Any]],
    ai_response_text: str,
):
    chat_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"
    chunks_json = json.dumps(retrieved_chunks)

    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO chat_history (id, user_query_text, retrieved_chunks, ai_response_text, created_at)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (chat_id, user_query_text, chunks_json, ai_response_text, created_at),
                    )
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Error saving chat history to DB: {e}")
        else:
            in_memory_store.chat_history.append({
                "id": chat_id,
                "user_query_text": user_query_text,
                "retrieved_chunks": retrieved_chunks,
                "ai_response_text": ai_response_text,
                "created_at": created_at,
            })
