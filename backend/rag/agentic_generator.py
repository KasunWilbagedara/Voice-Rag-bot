"""
rag/agentic_generator.py — Agentic LLM Reasoner (Backend 2 — Port 8001)
=========================================================================
Implements a multi-step agentic loop:

  Round 1:  LLM receives the user query + retrieved context.
            It may either answer directly OR emit a tool-call JSON.
  Round N:  Tool is executed → result is appended to the conversation.
            LLM is called again with the enriched context.
  Final:    When LLM produces a plain-text answer (no tool call), the loop ends.

Maximum iterations: MAX_AGENTIC_ROUNDS (default 5) to prevent infinite loops.

Exported functions:
  - agentic_query()   Full pipeline: embed → search → agentic loop → answer
"""

import json
import time
import logging
from typing import Any, Dict, List, Optional, Tuple

import openai
from google import genai
from google.genai import types

from backend.config import get_api_key, is_gemini_key
from backend.db import get_saved_chat_history
from backend.rag.prompts import build_language_instruction, build_system_prompt
from backend.rag.embedder import get_text_embedding as get_embedding
from backend.rag.retriever import search_similar_chunks
from backend.rag.generator import call_remote_tool

logger = logging.getLogger("voicerag.rag.agentic_generator")

MAX_AGENTIC_ROUNDS = 5

AGENTIC_GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-flash-lite-latest"]

# ---------------------------------------------------------------------------
# AGENTIC SYSTEM PROMPT
# ---------------------------------------------------------------------------

AGENTIC_SYSTEM_PROMPT = """You are an expert agentic AI assistant with access to live tools and a knowledge base.

CAPABILITIES:
- Search and reason over retrieved document knowledge
- Call tools to get live data (weather, order tracking, web search, math, datetime, students, SQL)
- Maintain conversation memory across turns
- Answer in the SAME language the user writes in (Sinhala or English)

TOOL CALLING FORMAT:
When you need a tool, output ONLY this JSON (no other text):
{
  "tool_call": {
    "name": "<tool_name>",
    "parameters": { "<param>": "<value>" }
  }
}

Available tools will be listed in the context.

ANSWER RULES:
1. After gathering all needed information (from context + tools), give a clear, helpful answer.
2. Do NOT make up information not present in context or tool results.
3. Cite source documents when answering from the knowledge base.
4. If you cannot find the answer, say so clearly.
5. Match the user's language (Sinhala or English).
"""

def _parse_tool_call(text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Returns (tool_name, parameters) if *text* is a tool-call JSON object
    (optionally wrapped in ``` fences or surrounded by text), else None.
    """
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    call = data.get("tool_call") if isinstance(data, dict) else None
    if isinstance(call, dict) and call.get("name"):
        return call["name"], call.get("parameters") or {}
    return None


# ---------------------------------------------------------------------------
# LLM Call (Gemini or OpenAI)
# ---------------------------------------------------------------------------

def _call_llm(messages: List[Dict[str, str]], api_key: str) -> str:
    """Single LLM call. Returns the assistant text response."""
    try:
        if is_gemini_key(api_key):
            client = genai.Client(api_key=api_key)
            # Convert messages to Gemini format
            history = []
            system_text = ""
            for m in messages:
                if m["role"] == "system":
                    system_text = m["content"]
                elif m["role"] == "user":
                    history.append(types.Content(role="user", parts=[types.Part(text=m["content"])]))
                elif m["role"] == "assistant":
                    history.append(types.Content(role="model", parts=[types.Part(text=m["content"])]))

            # Same active model fallback chain as the standard RAG generator.
            last_err: Optional[Exception] = None
            for model_name in AGENTIC_GEMINI_MODELS:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=history,
                        config=types.GenerateContentConfig(
                            system_instruction=system_text,
                            temperature=0.3,
                            max_output_tokens=2048,
                        ),
                    )
                    if response and response.text:
                        return response.text
                except Exception as e:
                    last_err = e
                    logger.debug("Agentic model %s failed: %s", model_name, e)
            raise RuntimeError(f"Gemini generation failed for all models: {last_err}")
        else:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )
            return response.choices[0].message.content or ""
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        raise


# ---------------------------------------------------------------------------
# Tool List Builder
# ---------------------------------------------------------------------------

def _build_tool_list_text() -> str:
    """Returns a formatted list of all registered tools for the LLM context."""
    try:
        from backend import tools as tools_module
        tool_list = tools_module.list_tools()
        lines = ["AVAILABLE TOOLS:"]
        for t in tool_list:
            params = ", ".join(t.get("param_names", []))
            lines.append(f"  - {t['name']}({params}): {t['description']}")
        return "\n".join(lines)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Agentic Loop
# ---------------------------------------------------------------------------

def _run_agentic_loop(
    user_query: str,
    context_text: str,
    chat_history: List[Dict],
    api_key: str,
) -> Tuple[str, List[Dict]]:
    """
    Multi-step agentic loop.

    Returns:
        (final_answer: str, tool_calls_made: List[Dict])
    """
    tool_list_text = _build_tool_list_text()

    system_content = (
        f"{AGENTIC_SYSTEM_PROMPT}\n\n"
        f"{tool_list_text}\n\n"
        f"RETRIEVED KNOWLEDGE BASE CONTEXT:\n{context_text}"
    )

    # Build initial message list
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

    # Inject last 6 turns of chat history
    for turn in chat_history[-6:]:
        role = turn.get("role", "user")
        if role not in ("user", "assistant"):
            role = "user"
        messages.append({"role": role, "content": turn.get("content", "")})

    # Add current user query
    messages.append({"role": "user", "content": user_query})

    tool_calls_made: List[Dict] = []

    for round_num in range(MAX_AGENTIC_ROUNDS):
        logger.info("Agentic round %d/%d", round_num + 1, MAX_AGENTIC_ROUNDS)

        llm_output = _call_llm(messages, api_key)

        # Check if the LLM wants to call a tool
        tool_call = _parse_tool_call(llm_output)
        if not tool_call:
            # No tool call — this is the final answer
            logger.info("Agentic loop complete in %d rounds", round_num + 1)
            return llm_output.strip(), tool_calls_made
        tool_name, tool_params = tool_call

        logger.info("Agentic: calling tool '%s' with params %s", tool_name, tool_params)

        # Execute the tool
        try:
            tool_result = call_remote_tool(tool_name, **tool_params)
            tool_result_str = json.dumps(tool_result, ensure_ascii=False, default=str)
        except Exception as e:
            tool_result = None
            tool_result_str = f"Tool error: {e}"

        tool_calls_made.append({
            "tool_name": tool_name,
            "parameters": tool_params,
            "result": tool_result,
        })

        # Append tool call + result to conversation
        messages.append({"role": "assistant", "content": llm_output})
        messages.append({
            "role": "user",
            "content": f"Tool '{tool_name}' result:\n{tool_result_str}\n\nNow provide your final answer based on all information gathered."
        })

    # Max rounds reached — ask for final answer
    messages.append({
        "role": "user",
        "content": "Please provide your final comprehensive answer now."
    })
    final = _call_llm(messages, api_key)
    return final.strip(), tool_calls_made


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def agentic_query(
    user_query: str,
    session_id: str = "default_user",
    top_k: int = 8,
    custom_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full agentic RAG pipeline:
      1. Embed query
      2. Hybrid search (dense + BM25)
      3. Build context from retrieved chunks
      4. Run agentic LLM loop (may call tools)
      5. Save answer to chat history
      6. Return structured response

    Args:
        user_query:      The user's question.
        session_id:      Conversation session identifier.
        top_k:           Number of chunks to retrieve.
        custom_api_key:  Optional API key override.

    Returns:
        Dict with keys: answer, retrievedChunks, toolCalls, sessionId, mode
    """
    start_time = time.time()
    api_key = get_api_key(custom_api_key)

    # 1. Embed query
    try:
        query_embedding = get_embedding(user_query, custom_api_key=api_key)
    except Exception as e:
        logger.error("Embedding failed: %s", e)
        query_embedding = []

    # 2. Hybrid search
    retrieved_chunks: List[Dict[str, Any]] = []
    if query_embedding:
        try:
            retrieved_chunks = search_similar_chunks(
                query_embedding=query_embedding,
                top_k=top_k,
                query_text=user_query,
                custom_api_key=custom_api_key,
            )
        except Exception as e:
            logger.warning("Retrieval failed: %s", e)

    # 3. Build context text
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks):
        title = chunk.get("documentTitle", "Unknown")
        content = chunk.get("content", "")
        context_parts.append(f"[SOURCE {i+1}: {title}]\n{content}")
    context_text = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."

    # 4. Load chat history
    chat_history: List[Dict] = []
    try:
        # Session-scoped history, returned newest-first.
        raw_history = get_saved_chat_history(limit=6, session_id=session_id)
        for turn in reversed(raw_history):
            chat_history.append({"role": "user", "content": turn.get("userQuery", "")})
            chat_history.append({"role": "assistant", "content": turn.get("aiResponse", "")})
    except Exception:
        pass

    # 5. Run agentic loop
    answer, tool_calls = _run_agentic_loop(
        user_query=user_query,
        context_text=context_text,
        chat_history=chat_history,
        api_key=api_key,
    )

    elapsed = time.time() - start_time
    logger.info(
        "Agentic query done in %.2fs | chunks=%d | tools=%d",
        elapsed, len(retrieved_chunks), len(tool_calls)
    )

    return {
        "answer": answer,
        "retrievedChunks": retrieved_chunks,
        "toolCalls": tool_calls,
        "sessionId": session_id,
        "mode": "agentic-rag",
        "processingTimeMs": int(elapsed * 1000),
    }
