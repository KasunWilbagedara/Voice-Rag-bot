"""
Live Web Search Tool.

Uses DuckDuckGo Instant Answer and Wikipedia REST API to search current events,
company profiles, facts, and definitions.
"""

import logging
import re
from typing import Dict, Any
import requests

from backend_with_tools.tools.base import register_tool

logger = logging.getLogger("voicerag.tools.web_search")


@register_tool(
    name="web_search",
    description="Live web search to find current information, facts, company profiles, news, and definitions from DuckDuckGo and Wikipedia.",
)
def web_search(query: str) -> Dict[str, Any]:
    """Live web search using DuckDuckGo Instant Answer and Wikipedia REST API."""
    clean_q = query.strip()
    if not clean_q:
        return {"error": "Search query is required."}

    # 1. DuckDuckGo Instant Answer
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={requests.utils.quote(clean_q)}&format=json&no_html=1&skip_disambig=1"
        ddg_res = requests.get(ddg_url, timeout=4).json()
        abstract = ddg_res.get("AbstractText")
        source_url = ddg_res.get("AbstractURL")
        heading = ddg_res.get("Heading")
        if abstract:
            return {
                "query": clean_q,
                "title": heading or clean_q,
                "summary": abstract,
                "source": source_url or "DuckDuckGo",
                "status": "success",
            }
    except Exception as ddg_err:
        logger.debug(f"DuckDuckGo search note: {ddg_err}")

    # 2. Wikipedia Summary API
    try:
        wiki_title = re.sub(r"[^a-zA-Z0-9_\s]", "", clean_q).strip().replace(" ", "_")
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_title}"
        wiki_res = requests.get(wiki_url, headers={"User-Agent": "VoiceRagBot/1.0"}, timeout=4).json()
        extract = wiki_res.get("extract")
        if extract:
            return {
                "query": clean_q,
                "title": wiki_res.get("title", clean_q),
                "summary": extract,
                "source": wiki_res.get("content_urls", {}).get("desktop", {}).get("page", "Wikipedia"),
                "status": "success",
            }
    except Exception as wiki_err:
        logger.debug(f"Wikipedia search note: {wiki_err}")

    return {
        "query": clean_q,
        "summary": f"No instant public web summary found for '{clean_q}'.",
        "status": "no_results",
    }
