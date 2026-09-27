"""
rag/generator.py — LLM Response Generator & Remote Tool Delegation
====================================================================
Contains:
  - call_remote_tool():       HTTP delegation to Tool Service (port 8001)
                              with local in-process fallback.
  - query_rag():              End-to-end RAG query pipeline (memory recall,
                              tool enrichment, LLM generation).
  - generate_rag_response():  Thin alias kept for backward compatibility.

Internal helpers (prefixed ``_``) are not exported.
"""

import re
import json
import time
import logging
import sqlite3
from typing import Any, Dict, List, Optional

import openai
from google import genai
from google.genai import types

from backend.config import get_api_key, is_gemini_key, TOOL_SERVICE_URL
from backend.db import (
    get_db_connection,
    SQLITE_DB_PATH,
    in_memory_store,
    get_saved_chat_history,
)
from backend.rag.prompts import build_language_instruction, build_system_prompt

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

logger = logging.getLogger("voicerag.rag.generator")


# ---------------------------------------------------------------------------
# Remote Tool Delegation
# ---------------------------------------------------------------------------

def call_remote_tool(tool_name: str, **kwargs) -> Any:
    """
    Delegates a tool call to the Tool Execution Service (Port 8001) via HTTP.

    Falls back to the local in-process ``tools.call_tool()`` if:
      - httpx is not installed
      - The Tool Service is unreachable (network timeout / connection error)
      - The Tool Service returns an HTTP error

    Args:
        tool_name: Registered tool name (e.g. ``'get_live_weather'``).
        **kwargs:  Keyword arguments forwarded to the tool as JSON.

    Returns:
        The tool's return value (dict, list, bool, etc.).
    """
    if _HTTPX_AVAILABLE:
        try:
            payload = {"tool_name": tool_name, "parameters": kwargs}
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(TOOL_SERVICE_URL, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result")
            logger.warning(
                "Tool Service returned %s for '%s'. Falling back to local execution.",
                resp.status_code,
                tool_name,
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as http_err:
            logger.warning(
                "Tool Service unreachable (%s). Falling back to local execution for '%s'.",
                http_err,
                tool_name,
            )

    # Local in-process fallback
    from backend import tools
    return tools.call_tool(tool_name, **kwargs)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _filter_relevant_memories(user_memories: List[Dict], user_query: str) -> List[Dict]:
    """Returns only the memory entries contextually relevant to *user_query*."""
    is_asking_order   = bool(re.search(r"order|ඇණවුම|tracking|status|ලැබෙන්නේ|බඩු|භාණ්ඩ|ord-\d+", user_query, re.IGNORECASE))
    is_asking_ticket  = bool(re.search(r"ticket|ටිකට්|complaint|පැමිණිල්ල|issue|tck-\d+", user_query, re.IGNORECASE))
    is_asking_student = bool(re.search(r"student|ශිෂ්‍ය|marks|ලකුණු|grade|ප්‍රතිඵල", user_query, re.IGNORECASE))
    is_asking_identity = bool(re.search(r"who am i|my name|මම කවුද|මගේ නම|මගේ විස්තර|remember|මතක", user_query, re.IGNORECASE))

    relevant = []
    for m in user_memories:
        k = m.get("key", "")
        if k == "last_tracked_order"   and not is_asking_order:   continue
        if k == "last_tracked_ticket"  and not is_asking_ticket:  continue
        if k == "last_tracked_student" and not is_asking_student: continue
        if k == "user_name" and not (is_asking_identity or "hello" in user_query.lower() or "ආයුබෝවන්" in user_query):
            continue
        relevant.append(m)
    return relevant


def _auto_extract_and_save_memory(user_query: str, session: str) -> None:
    """Silently persists identity & entity signals found in *user_query*."""
    try:
        is_question = bool(re.search(
            r"(\?|remember|recall|මතකද|ද\?|what|who|කවුද|මොකක්ද)", user_query, re.IGNORECASE
        ))
        if not is_question:
            name_match = re.search(
                r"(?:my name is|i am|call me|මගේ නම|මම)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|[a-zA-Z]+|[\u0D80-\u0DFF]+)",
                user_query, re.IGNORECASE,
            )
            if name_match:
                cand = name_match.group(1).strip()
                excluded = [
                    "asking", "inquiring", "checking", "looking", "here", "a", "the", "user",
                    "විමසන්නේ", "සහ", "හා", "මොකක්ද", "කුමක්ද", "මතකද", "කවුද", "who", "what"
                ]
                if cand.lower() not in excluded and len(cand) > 1:
                    call_remote_tool("save_session_memory", session_id=session, key="user_name", value=cand, category="identity")

        order_match = re.search(r"\b(ORD-\d{3,8})\b", user_query, re.IGNORECASE)
        if order_match:
            call_remote_tool("save_session_memory", session_id=session, key="last_tracked_order", value=order_match.group(1).upper(), category="entity")

        ticket_match = re.search(r"\b(TCK-\d{3,8})\b", user_query, re.IGNORECASE)
        if ticket_match:
            call_remote_tool("save_session_memory", session_id=session, key="last_tracked_ticket", value=ticket_match.group(1).upper(), category="entity")

        student_match = re.search(r"\b(STU\d{3,6})\b", user_query, re.IGNORECASE)
        if student_match:
            call_remote_tool("save_session_memory", session_id=session, key="last_tracked_student", value=student_match.group(1).upper(), category="entity")

        rem_match = re.search(
            r"(?:remember that|please remember|keep in mind|save this|මතක තබාගන්න|මතක තියාගන්න)\s+(.+)",
            user_query, re.IGNORECASE,
        )
        if rem_match:
            note_content = rem_match.group(1).strip()
            call_remote_tool("save_session_memory", session_id=session, key=f"custom_note_{int(time.time()) % 10000}", value=note_content, category="pinned_fact")
    except Exception as mem_err:
        logger.debug(f"Memory auto-extraction note: {mem_err}")


def _enrich_with_tools(
    user_query: str,
    retrieved_chunks: List[Dict[str, Any]],
) -> tuple[List[str], List[Dict[str, Any]]]:
    """
    Calls contextual tools (order tracking, weather, datetime, math, web
    search, student lookup, entity SQL scan) and returns:
      - db_context_blocks: formatted text strings for the system prompt
      - enriched_chunks:   additional chunk dicts injected into the context
    """
    db_context_blocks: List[str] = []
    enriched_chunks = list(retrieved_chunks)

    # 1. Order Tracking
    order_match = re.search(r"\b(ORD-\d{3,8})\b", user_query, re.IGNORECASE)
    if order_match:
        target_ord = order_match.group(1).upper()
        ord_res = call_remote_tool("track_customer_order", order_id=target_ord)
        if ord_res.get("status") == "found" and ord_res.get("order"):
            o = ord_res["order"]
            db_context_blocks.append(
                f"CUSTOMER ORDER TRACKING TOOL RECORD:\n"
                f"- Order ID: {o.get('order_id')}\n"
                f"- Customer ID: {o.get('customer_id')}\n"
                f"- Product: {o.get('product_name')}\n"
                f"- Amount: LKR {o.get('amount')}\n"
                f"- Status: {o.get('status')}\n"
                f"- Order Date: {o.get('order_date')}\n"
            )
            enriched_chunks.append({
                "id": f"tool_order_{target_ord}",
                "documentId": "tool_order_tracking",
                "documentTitle": f"Tool: Order Tracking ({target_ord})",
                "content": f"Order {target_ord} | Product: {o.get('product_name')} | Status: {o.get('status')} | Amount: LKR {o.get('amount')} | Date: {o.get('order_date')}",
                "chunkIndex": 0, "similarity": 1.0, "type": "tool_result",
            })

    # 2. Ticket Tracking
    ticket_match = re.search(r"\b(TCK-\d{3,8})\b", user_query, re.IGNORECASE)
    if ticket_match:
        target_tck = ticket_match.group(1).upper()
        tck_res = call_remote_tool("track_support_ticket", ticket_id=target_tck)
        if tck_res.get("status") == "found" and tck_res.get("ticket"):
            t = tck_res["ticket"]
            db_context_blocks.append(
                f"CUSTOMER SUPPORT TICKET TOOL RECORD:\n"
                f"- Ticket ID: {t.get('ticket_id')}\n"
                f"- Customer Name: {t.get('customer_name')}\n"
                f"- Category: {t.get('issue_category')}\n"
                f"- Description: {t.get('description')}\n"
                f"- Status: {t.get('resolution_status')}\n"
                f"- Priority: {t.get('priority')}\n"
            )
            enriched_chunks.append({
                "id": f"tool_ticket_{target_tck}",
                "documentId": "tool_ticket_tracking",
                "documentTitle": f"Tool: Support Ticket ({target_tck})",
                "content": f"Ticket {target_tck} | Category: {t.get('issue_category')} | Status: {t.get('resolution_status')} | Priority: {t.get('priority')}\nDescription: {t.get('description')}",
                "chunkIndex": 0, "similarity": 1.0, "type": "tool_result",
            })

    # 3. Live Weather
    if re.search(r"\b(weather|temperature|forecast|rain|climate|කාලගුණය|උෂ්ණත්වය|වැස්ස)\b", user_query, re.IGNORECASE):
        city_cand = "Colombo"
        city_match = re.search(r"\b(?:in|at|for|of)\s+([A-Za-z]+)\b", user_query, re.IGNORECASE)
        if city_match and city_match.group(1).lower() not in ["the", "today", "now", "here", "celsius"]:
            city_cand = city_match.group(1)
        w_res = call_remote_tool("get_live_weather", city=city_cand)
        if w_res.get("status") == "success":
            db_context_blocks.append(
                f"LIVE REAL-TIME WEATHER TOOL REPORT:\n"
                f"- City: {w_res.get('city')}, {w_res.get('country')}\n"
                f"- Current Temperature: {w_res.get('temperature_celsius')} °C\n"
                f"- Condition: {w_res.get('condition')}\n"
                f"- Wind Speed: {w_res.get('windspeed_kmh')} km/h\n"
                f"- Observed Time: {w_res.get('observation_time')}\n"
            )
            enriched_chunks.append({
                "id": f"tool_weather_{city_cand.lower()}",
                "documentId": "tool_weather",
                "documentTitle": f"Live Weather: {w_res.get('city')}",
                "content": f"Weather in {w_res.get('city')}: {w_res.get('temperature_celsius')}°C, {w_res.get('condition')}, Wind: {w_res.get('windspeed_kmh')} km/h",
                "chunkIndex": 0, "similarity": 1.0, "type": "tool_result",
            })

    # 4. Current DateTime
    if re.search(r"\b(what time|what date|current date|today's date|current time|what day|දැන් වෙලාව|දිනය|අද වෙලාව)\b", user_query, re.IGNORECASE):
        dt_res = call_remote_tool("get_current_datetime")
        if dt_res.get("status") == "success":
            db_context_blocks.append(
                f"SYSTEM REAL-TIME DATETIME TOOL:\n"
                f"- Current Date: {dt_res.get('readable_date')}\n"
                f"- Current Time: {dt_res.get('readable_time')}\n"
                f"- Day: {dt_res.get('day_of_week')}\n"
                f"- Timezone: {dt_res.get('timezone')}\n"
            )
            enriched_chunks.append({
                "id": "tool_datetime",
                "documentId": "tool_datetime",
                "documentTitle": "Tool: System Time & Date",
                "content": f"Current Time: {dt_res.get('readable_time')} | Date: {dt_res.get('readable_date')} ({dt_res.get('day_of_week')})",
                "chunkIndex": 0, "similarity": 1.0, "type": "tool_result",
            })

    # 5. Math Calculator
    math_match = re.search(r"\b(\d+(?:\.\d+)?\s*[\+\-\*\/]\s*\d+(?:\.\d+)?(?:\s*[\+\-\*\/]\s*\d+(?:\.\d+)?)*)\b", user_query)
    if math_match:
        expr = math_match.group(1)
        math_res = call_remote_tool("calculate_expression", expression=expr)
        if math_res.get("status") == "success":
            db_context_blocks.append(
                f"MATHEMATICAL CALCULATOR TOOL RESULT:\n"
                f"- Expression: {expr}\n"
                f"- Precise Computed Result: {math_res.get('result')}\n"
            )
            enriched_chunks.append({
                "id": "tool_math",
                "documentId": "tool_calculator",
                "documentTitle": "Tool: Accurate Math Calculator",
                "content": f"Expression: {expr} = {math_res.get('result')}",
                "chunkIndex": 0, "similarity": 1.0, "type": "tool_result",
            })

    # 6. Web Search fallback
    has_high_similarity_doc = any(c.get("similarity", 0) > 0.68 for c in retrieved_chunks)
    if not has_high_similarity_doc and len(user_query.split()) >= 2:
        is_search_intent = bool(re.search(r"\b(who is|what is|tell me about|history of|company|news|කවුද|මොකක්ද)\b", user_query, re.IGNORECASE))
        if is_search_intent:
            try:
                search_q = re.sub(r"\b(who is|what is|tell me about|please tell|can you tell|කවුද|මොකක්ද)\b", "", user_query, flags=re.IGNORECASE).strip()
                if search_q:
                    w_search = call_remote_tool("web_search", query=search_q)
                    if w_search.get("status") == "success" and w_search.get("summary"):
                        db_context_blocks.append(
                            f"LIVE WEB SEARCH TOOL RESULT ({w_search.get('source')}):\n"
                            f"- Query: {w_search.get('query')}\n"
                            f"- Title: {w_search.get('title')}\n"
                            f"- Summary: {w_search.get('summary')}\n"
                        )
                        enriched_chunks.append({
                            "id": "tool_web_search",
                            "documentId": "tool_web_search",
                            "documentTitle": f"Web Search: {w_search.get('title')}",
                            "content": f"Source: {w_search.get('source')}\nSummary: {w_search.get('summary')}",
                            "chunkIndex": 0, "similarity": 0.95, "type": "web_search",
                        })
            except Exception as w_err:
                logger.debug(f"Web search tool fallback note: {w_err}")

    # 7. Student Database Lookup
    student_record = call_remote_tool("lookup_student", search_term=user_query)
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
            "chunkIndex": 0, "similarity": 1.0, "type": "database_record",
        })

    # 8. Heuristic entity SQL scan
    try:
        query_words = [w.strip(",.'\"!?") for w in user_query.split() if len(w.strip(",.'\"!?")) >= 3]
        all_dbs = call_remote_tool("list_databases")
        for db in all_dbs:
            db_id = db["id"]
            schemas = call_remote_tool("get_database_schema", db_id=db_id)
            for schema in schemas:
                table_name = schema["table_name"]
                if table_name in ["documents", "document_chunks", "chat_history", "rag_documents", "rag_document_chunks", "rag_user_memories"]:
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
                        sql_res = call_remote_tool("execute_sql", sql_query=sql_stmt, db_id=db_id)
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
                                    "chunkIndex": 0, "similarity": 0.98, "type": "database_sql",
                                })
                    except Exception:
                        pass
    except Exception as db_err:
        logger.warning(f"DB entity matching note: {db_err}")

    return db_context_blocks, enriched_chunks


def _call_llm(
    system_prompt: str,
    user_query: str,
    api_key: str,
    model_name: str,
    provider: Optional[str],
    base_url: Optional[str],
) -> str:
    """Calls Gemini or OpenAI-compatible LLM and returns the generated text."""
    is_gemini = (provider == "gemini") or (is_gemini_key(api_key) and not provider and not base_url)

    if is_gemini and not base_url:
        client = genai.Client(api_key=api_key)
        full_prompt = f"{system_prompt}\n\nUSER QUESTION: {user_query}"
        models_to_try = []
        if model_name:
            models_to_try.append(model_name)
        for m in ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.6-flash"]:
            if m not in models_to_try:
                models_to_try.append(m)

        last_err = None
        for m_name in models_to_try:
            try:
                res = client.models.generate_content(
                    model=m_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=1536),
                )
                if res and res.text and res.text.strip():
                    return res.text.strip()
            except Exception as e:
                last_err = e

        raise RuntimeError(f"Gemini LLM generation failed: {last_err}")

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
        return ans.strip() if ans else ""


def _clean_generated_text(
    text: str,
    is_asking_order: bool,
    is_asking_ticket: bool,
    is_asking_identity: bool,
) -> str:
    """Strips robotic preambles and internal reasoning lines from LLM output."""
    clean_lines = []
    for line in text.splitlines():
        l_strip = line.strip()
        if l_strip.lower().startswith(
            ("thought ", "thought:", "thinking:", "reasoning:", "wait,", "wait ", "checklist:", "verification:")
        ):
            continue
        clean_lines.append(line)
    result = "\n".join(clean_lines).strip()

    if not is_asking_order and not is_asking_ticket and not is_asking_identity:
        result = re.sub(
            r"^(?:ඔව්\s+[^,]+,\s*)?ඔබගේ\s+මතක\s+සටහන්වල\s+ඇති\s+පරිදි\s+[^,\n]+(?:වන\s+අතර|වේ),?\s*",
            "",
            result,
            flags=re.IGNORECASE,
        ).strip()
        result = re.sub(
            r"^(?:yes\s+[^,]+,\s*)?as\s+recorded\s+in\s+your\s+(?:memory\s+notes|stored\s+records)\s+[^,\n]+(?:and|,)\s*",
            "",
            result,
            flags=re.IGNORECASE,
        ).strip()

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def query_rag(
    user_query: str,
    retrieved_chunks: List[Dict[str, Any]],
    custom_api_key: Optional[str] = None,
    model_name: str = "gemini-3.5-flash",
    target_language: str = "si",
    conversation_history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    session_id: Optional[str] = "default_user",
) -> Dict[str, Any]:
    """
    Full RAG pipeline: memory recall → tool enrichment → LLM generation.

    Steps:
      1. Auto-extract & persist entity signals from query (order/ticket/name).
      2. Fetch & filter user session memories.
      3. Call contextual tools (order tracking, weather, datetime, SQL, …).
      4. Build system prompt with all context layers.
      5. Generate answer via Gemini or OpenAI-compatible LLM.
      6. Clean and return the structured response.

    Args:
        user_query:           User's natural-language question.
        retrieved_chunks:     Dense/sparse vector search results from retriever.
        custom_api_key:       Optional per-request API key.
        model_name:           LLM model identifier.
        target_language:      ``"si"`` for Sinhala, anything else for English.
        conversation_history: Recent in-memory turn history.
        provider:             LLM provider override (``"gemini"``, ``"groq"``,
                              ``"ollama"``, ``"openrouter"``).
        base_url:             Custom OpenAI-compatible base URL.
        session_id:           User session identifier for persistent memory.

    Returns:
        ``{"answer": str, "retrievedChunks": list}``
    """
    api_key = get_api_key(custom_api_key)
    is_sinhala = target_language == "si"
    session = session_id or "default_user"

    # Step 1: persist memory signals
    _auto_extract_and_save_memory(user_query, session)

    # Step 2: fetch & filter memories
    user_memories = call_remote_tool("get_session_memories", session_id=session)
    is_asking_order    = bool(re.search(r"order|ඇණවුම|tracking|status|ලැබෙන්නේ|බඩු|භාණ්ඩ|ord-\d+", user_query, re.IGNORECASE))
    is_asking_ticket   = bool(re.search(r"ticket|ටිකට්|complaint|පැමිණිල්ල|issue|tck-\d+", user_query, re.IGNORECASE))
    is_asking_identity = bool(re.search(r"who am i|my name|මම කවුද|මගේ නම|මගේ විස්තර|remember|මතක", user_query, re.IGNORECASE))

    relevant_memories = _filter_relevant_memories(user_memories or [], user_query)
    memory_str = (
        "\n".join([f"- {m['key']}: {m['value']}" for m in relevant_memories])
        if relevant_memories
        else "No specific session memories relevant to this question."
    )

    # Step 3: tool enrichment
    db_context_blocks, enriched_chunks = _enrich_with_tools(user_query, retrieved_chunks)

    # Step 4: build conversation history string
    history_str = "No previous history."
    if conversation_history:
        recent = conversation_history[-6:]
        history_str = "\n".join(
            [f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}" for msg in recent]
        )
    else:
        past_turns = get_saved_chat_history(4)
        if past_turns:
            lines = []
            for t in reversed(past_turns):
                lines.append(f"USER: {t.get('userQuery', '')}")
                lines.append(f"ASSISTANT: {t.get('aiResponse', '')}")
            history_str = "\n".join(lines)

    # Step 5: build document context text
    doc_context_text = (
        "\n\n".join([
            f"[Source {idx+1}: Document '{chunk.get('documentTitle')}' (Doc ID: {chunk.get('documentId')})]\n{chunk.get('content')}"
            for idx, chunk in enumerate(retrieved_chunks[:8])
        ])
        if retrieved_chunks
        else "No document chunks retrieved."
    )

    db_context_str = "\n\n".join(db_context_blocks) if db_context_blocks else "No matching database records found."

    language_instruction = build_language_instruction(target_language)
    system_prompt = build_system_prompt(
        language_instruction=language_instruction,
        memory_str=memory_str,
        history_str=history_str,
        db_context_str=db_context_str,
        doc_context_text=doc_context_text,
    )

    # Step 6: LLM generation
    generated_text = _call_llm(
        system_prompt=system_prompt,
        user_query=user_query,
        api_key=api_key,
        model_name=model_name,
        provider=provider,
        base_url=base_url,
    )

    if generated_text:
        generated_text = _clean_generated_text(
            generated_text, is_asking_order, is_asking_ticket, is_asking_identity
        )

    return {
        "answer": generated_text,
        "retrievedChunks": enriched_chunks,
    }


def generate_rag_response(
    user_query: str,
    retrieved_chunks: List[Dict[str, Any]],
    custom_api_key: Optional[str] = None,
    model_name: str = "gemini-3.5-flash",
    target_language: str = "si",
    conversation_history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    session_id: Optional[str] = "default_user",
) -> Dict[str, Any]:
    """Backward-compatible alias for :func:`query_rag`."""
    return query_rag(
        user_query=user_query,
        retrieved_chunks=retrieved_chunks,
        custom_api_key=custom_api_key,
        model_name=model_name,
        target_language=target_language,
        conversation_history=conversation_history,
        provider=provider,
        base_url=base_url,
        session_id=session_id,
    )
