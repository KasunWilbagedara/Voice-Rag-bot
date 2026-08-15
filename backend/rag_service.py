import uuid
import re
import os
import json
import math
import sqlite3
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
    SQLITE_DB_PATH,
)
from backend import db_query_service

logger = logging.getLogger("voicerag.rag_service")

# Global cached embedding model & LRU caches
_CACHED_EMBEDDING_MODEL: Optional[str] = "models/gemini-embedding-001"
_EMBEDDING_CACHE: Dict[str, List[float]] = {}

PREFERRED_GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.7-flash",
    "gemini-flash-latest",
]


# --- 1. RECURSIVE STRUCTURAL CHUNKING ---
def recursive_structural_chunk(
    text: str,
    target_size: int = 500,
    overlap: int = 90,
) -> List[str]:
    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    sections = re.split(r"(?=\n#{1,3}\s+|\n--- Page \d+ ---\n|\n### Slide \d+|\n### Sheet:)", cleaned)
    chunks: List[str] = []

    for section in sections:
        sec_text = section.strip()
        if not sec_text:
            continue

        if len(sec_text) <= target_size + overlap:
            if len(sec_text) > 8:
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
                    if current_chunk and len(current_chunk) > 8:
                        chunks.append(current_chunk.strip())

                    if len(para_clean) > target_size:
                        sentences = re.split(r"(?<=[.!?;])\s+", para_clean)
                        sub_chunk = ""
                        for sent in sentences:
                            if len(sub_chunk) + len(sent) + 1 <= target_size:
                                sub_chunk += (" " if sub_chunk else "") + sent
                            else:
                                if sub_chunk and len(sub_chunk) > 8:
                                    chunks.append(sub_chunk.strip())
                                sub_chunk = sent
                        if sub_chunk and len(sub_chunk) > 8:
                            chunks.append(sub_chunk.strip())
                        current_chunk = ""
                    else:
                        current_chunk = para_clean

            if current_chunk and len(current_chunk) > 8:
                chunks.append(current_chunk.strip())

    return chunks if chunks else [cleaned[:target_size]]


# --- 2. HIGH-PRECISION EMBEDDING ENGINE ---
def get_embedding(text: str, custom_api_key: Optional[str] = None) -> List[float]:
    global _CACHED_EMBEDDING_MODEL, _EMBEDDING_CACHE
    cleaned_text = text.replace("\n", " ").strip()
    cache_key = f"{custom_api_key or 'default'}_{hash(cleaned_text)}"

    if cache_key in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[cache_key]

    api_key = get_api_key(custom_api_key)

    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
        
        models_to_try = [
            "models/gemini-embedding-001",
            "models/gemini-embedding-2",
        ]

        for m in models_to_try:
            try:
                res = client.models.embed_content(model=m, contents=cleaned_text)
                emb = res.embedding.values if hasattr(res, "embedding") and res.embedding else res.embeddings[0].values
                if emb and len(emb) > 0:
                    _CACHED_EMBEDDING_MODEL = m
                    _EMBEDDING_CACHE[cache_key] = list(emb)
                    return list(emb)
            except Exception as e:
                logger.debug(f"Embedding model {m} note: {e}")
                continue

        logger.warning("Gemini embedding calls failed. Using deterministic fallback vector.")
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
        target_model = _CACHED_EMBEDDING_MODEL or "models/gemini-embedding-001"
        embeddings = []
        for t in cleaned_texts:
            try:
                res = client.models.embed_content(model=target_model, contents=t)
                emb = res.embedding.values if hasattr(res, "embedding") and res.embedding else res.embeddings[0].values
                embeddings.append(list(emb))
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


# --- 3. PERSISTENT DOCUMENT INGESTION (Database + SQLite) ---
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

    # 1. Save to SQLite persistent database
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO rag_documents (id, title, file_type, created_at) VALUES (?, ?, ?, ?);",
            (doc_id, title, file_type, created_at),
        )
        for i, (chunk, emb) in enumerate(zip(raw_chunks, embeddings)):
            chunk_id = str(uuid.uuid4())
            emb_json = json.dumps(emb)
            cur.execute(
                """INSERT INTO rag_document_chunks (id, document_id, content, chunk_index, embedding, created_at)
                   VALUES (?, ?, ?, ?, ?, ?);""",
                (chunk_id, doc_id, chunk, i, emb_json, created_at),
            )
        conn.commit()
        conn.close()
        logger.info(f"Successfully ingested document '{title}' into SQLite database ({len(raw_chunks)} chunks).")
    except Exception as e:
        logger.error(f"Error persisting document to SQLite: {e}")

    # 2. Also save to PostgreSQL pgvector if connected
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
                    logger.info(f"Successfully ingested document '{title}' into PostgreSQL DB.")
            except Exception as e:
                conn.rollback()
                logger.warning(f"PostgreSQL ingestion note: {e}")

    # 3. Update in-memory cache
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


# --- 4. BM25 SPARSE KEYWORD SEARCH ---
def bm25_search_in_database(query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
    tokens = [w.lower() for w in re.findall(r"\w+", query_text) if len(w) > 2]
    if not tokens:
        return []

    results = []
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


# --- 5. ADVANCED CROSS-LINGUAL HYBRID RRF SEARCH ENGINE ---
def search_vector_database(
    query_embedding: List[float],
    top_k: int = 8,
    query_text: Optional[str] = None,
    custom_api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query_str = query_text or ""
    dense_results: List[Dict[str, Any]] = []

    # 1. Search PostgreSQL if connected
    with get_db_connection() as conn:
        if conn:
            try:
                with conn.cursor() as cur:
                    vector_str = f"[{','.join(map(str, query_embedding))}]"
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
            except Exception as e:
                logger.debug(f"PostgreSQL vector search note: {e}")

    # 2. Search SQLite Database chunks using Cosine Similarity
    if not dense_results:
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                SELECT c.id, c.document_id, d.title, c.content, c.chunk_index, c.embedding
                FROM rag_document_chunks c
                JOIN rag_documents d ON c.document_id = d.id;
            """)
            rows = cur.fetchall()
            conn.close()

            scored = []
            for r in rows:
                try:
                    chunk_emb = json.loads(r[5])
                    sim = cosine_similarity(query_embedding, chunk_emb)
                    scored.append({
                        "id": r[0],
                        "documentId": r[1],
                        "documentTitle": r[2],
                        "content": r[3],
                        "chunkIndex": r[4],
                        "similarity": sim,
                    })
                except Exception:
                    continue

            scored.sort(key=lambda x: x["similarity"], reverse=True)
            dense_results = scored[: top_k * 2]
        except Exception as e:
            logger.debug(f"SQLite vector search note: {e}")

    # 3. Hybrid BM25 keyword search
    bm25_results = bm25_search_in_database(query_str, top_k=top_k)

    # 4. Reciprocal Rank Fusion (RRF)
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


# --- 6. TEXT-TO-SQL QUERY GENERATOR ---
def generate_llm_sql_query(
    user_query: str,
    schemas_summary: str,
    custom_api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """Uses LLM to convert user natural language questions into safe read-only SQL queries."""
    if not schemas_summary or not user_query:
        return None

    api_key = get_api_key(custom_api_key)

    extracted_ids = re.findall(r"\b[A-Za-z0-9]+[-_][A-Za-z0-9]+\b|\bSTU\d+\b|\bORD\d+\b|\b\d{3,10}\b", user_query, re.IGNORECASE)
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

    def parse_sql_output(text: str) -> Optional[Tuple[str, str]]:
        if not text or "NONE" in text.strip().upper():
            return None

        cleaned = re.sub(r"```(?:sql)?", "", text).replace("```", "").strip()
        db_match = re.search(r"DB_ID:\s*([^\n\r]+)", cleaned, re.IGNORECASE)
        sql_match = re.search(r"SQL:\s*(SELECT[\s\S]+)", cleaned, re.IGNORECASE)

        if db_match and sql_match:
            db_id = db_match.group(1).strip().strip("'\"`")
            sql_stmt = sql_match.group(2).strip().rstrip(";") + ";"
            return db_id, sql_stmt

        select_match = re.search(r"(SELECT[\s\S]+?;)", cleaned, re.IGNORECASE)
        if select_match:
            first_db_id = "customer_support_db" if "customer_support_db" in schemas_summary else "primary_db"
            return first_db_id, select_match.group(1).strip()

        return None

    try:
        is_gemini = (provider == "gemini") or (is_gemini_key(api_key) and not provider and not base_url)

        if is_gemini and not base_url:
            client = genai.Client(api_key=api_key)
            models_to_try = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
            for m in models_to_try:
                try:
                    res = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=200)
                    )
                    if res and res.text:
                        parsed = parse_sql_output(res.text)
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

            client_kwargs = {}
            client_kwargs["api_key"] = api_key if api_key else "ollama"
            if resolved_base_url:
                client_kwargs["base_url"] = resolved_base_url

            client = openai.OpenAI(**client_kwargs)
            active_model = model_name or "gpt-4o-mini"
            completion = client.chat.completions.create(
                model=active_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            text = completion.choices[0].message.content
            if text:
                parsed = parse_sql_output(text)
                if parsed:
                    return parsed
    except Exception as e:
        logger.debug(f"Text-to-SQL note: {e}")

    return None


# --- 7. HIGH-ACCURACY LLM GENERATION & FACTUAL FUSION ---
def generate_voice_rag_answer(
    user_query: str,
    retrieved_chunks: List[Dict[str, Any]],
    custom_api_key: Optional[str] = None,
    model_name: str = "gemini-3.5-flash",
    target_language: str = "si",
    conversation_history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    api_key = get_api_key(custom_api_key)
    is_sinhala = target_language == "si"
    db_context_blocks = []
    enriched_chunks = list(retrieved_chunks)

    # 1. Direct Student Database Lookup
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

    # 2. Heuristic Entity Scan & Text-to-SQL
    try:
        query_words = [w.strip(",.'\"!?") for w in user_query.split() if len(w.strip(",.'\"!?")) >= 3]
        all_dbs = db_query_service.db_manager.list_databases()

        for db in all_dbs:
            db_id = db["id"]
            schemas = db_query_service.db_manager.get_database_schema(db_id)
            for schema in schemas:
                table_name = schema["table_name"]
                if table_name in ["documents", "document_chunks", "chat_history", "rag_documents", "rag_document_chunks"]:
                    continue

                col_names = [c["column"] for c in schema["columns"]]
                clauses = []
                for qw in query_words:
                    if qw.lower() in ["the", "what", "is", "of", "for", "and", "how", "කුමක්ද", "කියන්න", "විස්තර"]:
                        continue
                    for col in col_names:
                        clauses.append(f"LOWER(CAST({col} AS TEXT)) LIKE '%{qw.lower()}%'")

                if clauses:
                    sql_stmt = f"SELECT * FROM {table_name} WHERE {' OR '.join(clauses)} LIMIT 6;"
                    try:
                        sql_res = db_query_service.db_manager.execute_safe_sql(sql_stmt, db_id=db_id)
                        if sql_res and sql_res.get("rows") and len(sql_res["rows"]) > 0:
                            rows_data = sql_res["rows"]
                            block_text = f"DATABASE '{db['name']}' -> TABLE '{table_name}':\n" + json.dumps(rows_data[:5], indent=2)
                            if block_text not in db_context_blocks:
                                db_context_blocks.append(block_text)
                                enriched_chunks.append({
                                    "id": f"db_entity_{db_id}_{table_name}",
                                    "documentId": f"db_{db_id}",
                                    "documentTitle": f"Database: {db['name']} ({table_name})",
                                    "content": f"Table: {table_name}\nMatching Records:\n" + json.dumps(rows_data[:5]),
                                    "chunkIndex": 0,
                                    "similarity": 0.98,
                                    "type": "database_sql"
                                })
                    except Exception:
                        pass
    except Exception as db_err:
        logger.warning(f"DB entity matching note: {db_err}")

    # Build prompt context
    db_context_str = "\n\n".join(db_context_blocks) if db_context_blocks else "No matching database records found."

    history_str = "No previous history."
    if conversation_history:
        recent_history = conversation_history[-6:]
        history_lines = [f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}" for msg in recent_history]
        history_str = "\n".join(history_lines)

    if retrieved_chunks:
        doc_context_text = "\n\n".join([
            f"[Source {idx+1}: Document '{chunk.get('documentTitle')}' (Doc ID: {chunk.get('documentId')})]\n{chunk.get('content')}"
            for idx, chunk in enumerate(retrieved_chunks[:8])
        ])
    else:
        doc_context_text = "No document chunks retrieved."

    if is_sinhala:
        language_instruction = (
            "CRITICAL SINHALA ACCURACY & COMPLETENESS REQUIREMENT:\n"
            "Synthesize a complete, thorough, and highly accurate answer in natural, fluent SINHALA (සිංහල).\n"
            "Strictly use the STRUCTURED DATABASE RECORDS and CONTEXT DOCUMENTS provided below.\n\n"
            "RULES FOR SINHALA RESPONSE:\n"
            "1. Answer the question COMPLETELY and thoroughly. Never leave sentences unfinished or cut off.\n"
            "2. State key facts, points, names, numbers, statuses, and explanations clearly and comprehensively.\n"
            "3. If comparing numbers or statistical data, append a hidden JSON chart schema at the very end inside ```json ... ``` code block.\n"
            "4. Do NOT output internal evaluation notes, verification steps, or meta commentary."
        )
    else:
        language_instruction = (
            "CRITICAL ACCURACY & COMPLETENESS REQUIREMENT:\n"
            "Deliver a complete, comprehensive, and 100% accurate answer grounded strictly in the STRUCTURED DATABASE RECORDS and CONTEXT DOCUMENTS below.\n\n"
            "RULES FOR RESPONSE:\n"
            "1. Answer the question COMPLETELY and thoroughly. Explain all requested topics, challenges, points, and facts in full detail. Never leave sentences unfinished or cut off.\n"
            "2. State key facts directly (Order IDs, amounts, statuses, customer names, GPA, policies, root causes).\n"
            "3. If comparing numbers or statistics, append a hidden JSON chart schema at the very end inside ```json ... ``` code block.\n"
            "4. Do NOT output internal evaluation notes, verification steps, or meta commentary."
        )

    system_prompt = (
        f"You are an exceptionally smart, articulate, and accurate AI Voice & Knowledge Assistant powering an enterprise Multi-DB & Multi-Doc Voice-RAG system.\n\n"
        f"{language_instruction}\n\n"
        f"PREVIOUS CONVERSATION HISTORY:\n{history_str}\n\n"
        f"CONNECTED STRUCTURED DATABASE RECORDS:\n{db_context_str}\n\n"
        f"UNSTRUCTURED CONTEXT DOCUMENTS:\n{doc_context_text}"
    )

    generated_text = ""
    is_gemini = (provider == "gemini") or (is_gemini_key(api_key) and not provider and not base_url)

    if is_gemini and not base_url:
        client = genai.Client(api_key=api_key)
        full_prompt = f"{system_prompt}\n\nUSER QUESTION: {user_query}"

        models_to_try = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
        last_err = None
        for m_name in models_to_try:
            try:
                res = client.models.generate_content(
                    model=m_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=2048,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
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
        resolved_base_url = base_url
        if provider == "groq" and not resolved_base_url:
            resolved_base_url = "https://api.groq.com/openai/v1"
        elif provider == "ollama" and not resolved_base_url:
            resolved_base_url = "http://localhost:11434/v1"
        elif provider == "openrouter" and not resolved_base_url:
            resolved_base_url = "https://openrouter.ai/api/v1"

        client_kwargs = {}
        client_kwargs["api_key"] = api_key if api_key else "ollama"
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url

        client = openai.OpenAI(**client_kwargs)
        active_model = model_name or "gpt-4o-mini"
        completion = client.chat.completions.create(
            model=active_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ],
            temperature=0.2,
            max_tokens=2048,
        )
        ans = completion.choices[0].message.content
        generated_text = ans.strip() if ans else ("පිළිතුරක් සෑදීමට නොහැකි විය." if is_sinhala else "I could not generate a response.")

    if generated_text:
        clean_lines = []
        for line in generated_text.splitlines():
            l_strip = line.strip()
            if l_strip.lower().startswith(("thought ", "thought:", "thinking:", "reasoning:", "wait,", "wait ", "checklist:", "verification:")):
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

    # 1. Save to SQLite database
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO rag_chat_history (id, user_query_text, retrieved_chunks, ai_response_text, created_at)
               VALUES (?, ?, ?, ?, ?);""",
            (chat_id, user_query_text, chunks_json, ai_response_text, created_at),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"SQLite chat history save note: {e}")

    # 2. Save to PostgreSQL if connected
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
                logger.debug(f"PostgreSQL chat history save note: {e}")

    in_memory_store.chat_history.append({
        "id": chat_id,
        "user_query_text": user_query_text,
        "retrieved_chunks": retrieved_chunks,
        "ai_response_text": ai_response_text,
        "created_at": created_at,
    })
