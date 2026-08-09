import uuid
import re
import json
import math
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

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


# --- 3. FAST EMBEDDING ENGINE ---
def get_embedding(text: str, custom_api_key: Optional[str] = None) -> List[float]:
    global _CACHED_EMBEDDING_MODEL
    api_key = get_api_key(custom_api_key)
    cleaned_text = text.replace("\n", " ")

    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
        if _CACHED_EMBEDDING_MODEL:
            try:
                res = client.models.embed_content(model=_CACHED_EMBEDDING_MODEL, contents=cleaned_text)
                return res.embedding.values if hasattr(res, "embedding") and res.embedding else res.embeddings[0].values
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
                return res.embedding.values if hasattr(res, "embedding") and res.embedding else res.embeddings[0].values
            except Exception:
                continue

        raise RuntimeError("Gemini embedding failed.")
    else:
        client = openai.OpenAI(api_key=api_key)
        res = client.embeddings.create(
            model="text-embedding-3-small",
            input=cleaned_text,
            encoding_format="float",
        )
        return res.data[0].embedding


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

    conn = get_db_connection()
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
        finally:
            conn.close()
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
    conn = get_db_connection()

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
        finally:
            conn.close()
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


# --- 7. HIGH-INTELLIGENCE LLM GENERATOR (google-genai SDK) ---
def generate_voice_rag_answer(
    user_query: str,
    retrieved_chunks: List[Dict[str, Any]],
    custom_api_key: Optional[str] = None,
    model_name: str = "gemini-flash-latest",
    target_language: str = "si",
) -> str:
    api_key = get_api_key(custom_api_key)
    is_sinhala = target_language == "si"

    if retrieved_chunks:
        context_text = "\n\n".join([
            f"--- DOCUMENT CHUNK {idx + 1} ({chunk.get('documentTitle', 'Doc')}) ---\n{chunk.get('content', '')}"
            for idx, chunk in enumerate(retrieved_chunks[:8])
        ])
    else:
        context_text = "No document uploaded yet."

    if is_sinhala:
        language_instruction = (
            "CRITICAL SINHALA VOICE & ACCURACY REQUIREMENT:\n"
            "You MUST synthesize a comprehensive, smart, and highly articulate answer in natural, fluent SINHALA (සිංහල).\n"
            "Thoroughly analyze the CONTEXT DOCUMENTS provided below. Extract all main topics, case study details, project team issues, facts, or findings, and explain them clearly in Sinhala.\n\n"
            "RULES FOR SINHALA RESPONSE:\n"
            "1. Deliver a COMPLETE 3 to 6 sentence spoken response. NEVER leave your sentence incomplete or cut off!\n"
            "2. If asked about a case study or summary ('මේකේ කේස්ස්ටඩියගැන පැහැදිලි කරන්න'), summarize the core problem, context, team conflict, or solution clearly.\n"
            "3. Do NOT use markdown symbols (*, #, -, ```), no bullet points, and no citations like [1] or [Source 1], as your response will be read aloud."
        )
    else:
        language_instruction = (
            "CRITICAL VOICE & ACCURACY REQUIREMENT:\n"
            "Deliver an intelligent, comprehensive, and highly accurate answer grounded strictly in the CONTEXT DOCUMENTS below.\n\n"
            "RULES FOR RESPONSE:\n"
            "1. Synthesize a COMPLETE 3 to 6 sentence spoken response summarizing main facts, case studies, or findings.\n"
            "2. Do NOT use markdown symbols (*, #, -, ```), no bullet points, and no citations."
        )

    system_prompt = (
        f"You are an exceptionally smart, articulate, and accurate AI Voice Assistant powering an enterprise Voice-RAG system.\n\n"
        f"{language_instruction}\n\n"
        f"CONTEXT DOCUMENTS:\n{context_text}"
    )

    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
        full_prompt = f"{system_prompt}\n\nUSER QUESTION: {user_query}"

        # Valid Gemini models supporting generateContent in google-genai
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
                    return res.text.strip()
            except Exception as e:
                last_err = e

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
        return ans.strip() if ans else ("පිළිතුරක් සෑදීමට නොහැකි විය." if is_sinhala else "I could not generate a response.")


def save_chat_history(
    user_query_text: str,
    retrieved_chunks: List[Dict[str, Any]],
    ai_response_text: str,
):
    chat_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"
    chunks_json = json.dumps(retrieved_chunks)

    conn = get_db_connection()
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
        finally:
            conn.close()
    else:
        in_memory_store.chat_history.append({
            "id": chat_id,
            "user_query_text": user_query_text,
            "retrieved_chunks": retrieved_chunks,
            "ai_response_text": ai_response_text,
            "created_at": created_at,
        })
