"""
rag_v2/core/generator.py
------------------------
Streaming and non-streaming LLM response generator with citations.

Supports both Google Gemini and OpenAI backends, selected automatically
from the resolved API key.

SSE event types yielded by generate_stream():
  - {"type": "text",     "content": "<text fragment>"}
  - {"type": "citation", "citations": [...]}
  - {"type": "done"}
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from rag_v2.config import GEMINI_MODEL, OPENAI_MODEL, get_api_key, is_gemini_key

logger = logging.getLogger("rag_v2.core.generator")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a knowledgeable, multilingual assistant. "
    "Always respond in the same language the user uses. "
    "Use the provided context passages to answer questions accurately and concisely. "
    "Cite your sources using [SOURCE: <title>, chunk <N>] notation when drawing "
    "from the context. "
    "If the context does not contain enough information to answer confidently, "
    "say so clearly and offer what partial information you can. "
    "You may use tool results (weather, database queries, web search) if they "
    "are included in the context to provide real-time or structured data. "
    "Be helpful, accurate, and conversational."
)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    tool_results: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Assemble the full prompt sent to the LLM.

    Parameters
    ----------
    query : str
        Current user query.
    chunks : List[Dict]
        Reranked context chunks (each must have 'content', 'document_title',
        'chunk_index' keys).
    history : List[Dict]
        Conversation history dicts with 'role' and 'content' keys.
        Only the last 6 turns are included.
    tool_results : List[Dict], optional
        Results from tool calls (weather, SQL, search, …).

    Returns
    -------
    str
        Formatted prompt string.
    """
    sections: List[str] = []

    # --- Context passages ---
    if chunks:
        context_lines = ["### Context Passages\n"]
        for i, chunk in enumerate(chunks, start=1):
            title = chunk.get("document_title", "Unknown")
            idx = chunk.get("chunk_index", i - 1)
            content = chunk.get("content", "").strip()
            context_lines.append(
                f"[SOURCE: {title}, chunk {idx}]\n{content}\n"
            )
        sections.append("\n".join(context_lines))

    # --- Tool results ---
    if tool_results:
        tool_lines = ["### Tool Results\n"]
        for tr in tool_results:
            tool_name = tr.get("tool", "tool")
            result_data = tr.get("result", "")
            if isinstance(result_data, dict):
                result_data = json.dumps(result_data, ensure_ascii=False, indent=2)
            tool_lines.append(f"[{tool_name.upper()}]\n{result_data}\n")
        sections.append("\n".join(tool_lines))

    # --- Conversation history (last 6 turns) ---
    recent_history = history[-6:] if len(history) > 6 else history
    if recent_history:
        history_lines = ["### Conversation History\n"]
        for turn in recent_history:
            role = turn.get("role", "user").capitalize()
            content = turn.get("content", "").strip()
            history_lines.append(f"{role}: {content}")
        sections.append("\n".join(history_lines))

    # --- Current question ---
    sections.append(f"### Question\n{query}")

    # --- Instruction ---
    sections.append(
        "### Answer\n"
        "Answer the question using the context above. "
        "Cite relevant sources with [SOURCE: title, chunk N] notation."
    )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Citation extraction
# ---------------------------------------------------------------------------

def extract_citations(
    chunks: List[Dict[str, Any]],
    answer: str,  # noqa: ARG001  (reserved for future substring matching)
) -> List[Dict[str, Any]]:
    """
    Build a citation list from the chunks that were included in the prompt.

    Currently returns all chunks (they were all used to build context).
    The *answer* parameter is kept for future substring-matching refinement.

    Returns
    -------
    List[Dict]
        Each dict has: document_id, document_title, chunk_index,
        content (first 200 chars), similarity_score.
    """
    citations: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for chunk in chunks:
        cid = str(chunk.get("id", ""))
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        citations.append(
            {
                "document_id": chunk.get("document_id"),
                "document_title": chunk.get("document_title", "Unknown"),
                "chunk_index": chunk.get("chunk_index", 0),
                "content": chunk.get("content", "")[:200],
                "similarity_score": round(float(chunk.get("similarity", 0.0)), 4),
            }
        )
    return citations


# ---------------------------------------------------------------------------
# Internal LLM call helpers (synchronous, run in executor for async wrapper)
# ---------------------------------------------------------------------------

def _generate_gemini(full_prompt: str, api_key: str) -> str:
    """Non-streaming Gemini generation."""
    from google import genai  # type: ignore

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=full_prompt,
        config={"system_instruction": SYSTEM_PROMPT},
    )
    return response.text or ""


def _generate_openai(full_prompt: str, api_key: str) -> str:
    """Non-streaming OpenAI generation."""
    import openai  # type: ignore

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content or ""


def _stream_gemini(full_prompt: str, api_key: str):
    """Yield text chunks from Gemini streaming response (synchronous generator)."""
    from google import genai  # type: ignore

    client = genai.Client(api_key=api_key)
    for chunk in client.models.generate_content_stream(
        model=GEMINI_MODEL,
        contents=full_prompt,
        config={"system_instruction": SYSTEM_PROMPT},
    ):
        if chunk.text:
            yield chunk.text


def _stream_openai(full_prompt: str, api_key: str):
    """Yield text chunks from OpenAI streaming response (synchronous generator)."""
    import openai  # type: ignore

    client = openai.OpenAI(api_key=api_key)
    stream = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0.3,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


# ---------------------------------------------------------------------------
# Public API – non-streaming
# ---------------------------------------------------------------------------

def generate_answer(
    query: str,
    chunks: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    tool_results: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generate a complete answer (non-streaming).

    Parameters
    ----------
    query : str
        User query.
    chunks : List[Dict]
        Reranked context chunks.
    history : List[Dict]
        Conversation history.
    api_key : str, optional
        API key; resolved from config if omitted.
    tool_results : List[Dict], optional
        Optional tool call results to include in context.

    Returns
    -------
    Tuple[str, List[Dict]]
        (answer_text, citations)
    """
    resolved_key = api_key or get_api_key()
    use_gemini = resolved_key and is_gemini_key(resolved_key)

    full_prompt = build_prompt(query, chunks, history, tool_results)
    logger.debug(
        "generate_answer: provider=%s, prompt_len=%d",
        "gemini" if use_gemini else "openai",
        len(full_prompt),
    )

    try:
        if use_gemini:
            answer = _generate_gemini(full_prompt, resolved_key)
        else:
            answer = _generate_openai(full_prompt, resolved_key)
    except Exception as exc:  # noqa: BLE001
        logger.error("generate_answer failed: %s", exc, exc_info=True)
        raise

    citations = extract_citations(chunks, answer)
    logger.info("generate_answer: produced %d-char answer with %d citations", len(answer), len(citations))
    return answer, citations


# ---------------------------------------------------------------------------
# Public API – streaming
# ---------------------------------------------------------------------------

async def generate_stream(
    query: str,
    chunks: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    tool_results: Optional[List[Dict[str, Any]]] = None,
) -> AsyncGenerator[str, None]:
    """
    Async generator that streams the LLM response as SSE-formatted strings.

    Each yielded value is a complete SSE line:
      ``data: {json_payload}\\n\\n``

    Event types:
      - ``{"type": "text",     "content": "<fragment>"}``
      - ``{"type": "citation", "citations": [...]}``
      - ``{"type": "done"}``

    Parameters
    ----------
    query : str
        User query.
    chunks : List[Dict]
        Reranked context chunks.
    history : List[Dict]
        Conversation history.
    api_key : str, optional
        API key; resolved from config if omitted.
    tool_results : List[Dict], optional
        Optional tool call results to include in context.

    Yields
    ------
    str
        SSE-formatted data lines.
    """
    resolved_key = api_key or get_api_key()
    use_gemini = resolved_key and is_gemini_key(resolved_key)

    full_prompt = build_prompt(query, chunks, history, tool_results)
    logger.debug(
        "generate_stream: provider=%s, prompt_len=%d",
        "gemini" if use_gemini else "openai",
        len(full_prompt),
    )

    collected_text: List[str] = []

    def _sse(payload: Dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    try:
        loop = asyncio.get_event_loop()

        if use_gemini:
            sync_gen = _stream_gemini(full_prompt, resolved_key)
        else:
            sync_gen = _stream_openai(full_prompt, resolved_key)

        # Run synchronous generator in a thread, yield text tokens as they arrive
        def _drain_sync_gen():
            """Pull all items from the sync generator; called in executor."""
            return list(sync_gen)

        # For true streaming, iterate via a queue bridging sync → async
        import queue as _queue
        import threading

        token_queue: "_queue.Queue[Optional[str]]" = _queue.Queue()

        def _producer():
            try:
                if use_gemini:
                    for text_fragment in _stream_gemini(full_prompt, resolved_key):
                        token_queue.put(text_fragment)
                else:
                    for text_fragment in _stream_openai(full_prompt, resolved_key):
                        token_queue.put(text_fragment)
            except Exception as exc:  # noqa: BLE001
                logger.error("Streaming producer thread error: %s", exc, exc_info=True)
                token_queue.put(None)
                return
            token_queue.put(None)  # sentinel

        producer_thread = threading.Thread(target=_producer, daemon=True)
        producer_thread.start()

        while True:
            try:
                fragment = await loop.run_in_executor(None, token_queue.get, True, 0.05)
            except _queue.Empty:
                await asyncio.sleep(0)
                continue

            if fragment is None:
                break  # sentinel received – stream finished

            collected_text.append(fragment)
            yield _sse({"type": "text", "content": fragment})

        producer_thread.join(timeout=5)

    except Exception as exc:  # noqa: BLE001
        logger.error("generate_stream failed: %s", exc, exc_info=True)
        yield _sse({"type": "error", "message": str(exc)})

    # Emit citations
    full_answer = "".join(collected_text)
    citations = extract_citations(chunks, full_answer)
    yield _sse({"type": "citation", "citations": citations})

    # Emit done
    yield _sse({"type": "done"})
    logger.info(
        "generate_stream: finished streaming %d chars, %d citations",
        len(full_answer),
        len(citations),
    )
