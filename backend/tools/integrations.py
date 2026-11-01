"""
tools/integrations.py — LangChain & Composio Integration
==========================================================
Provides:
  - get_langchain_tools()  — converts all registry tools to LangChain
                             ``StructuredTool`` instances.
  - load_composio_tools()  — loads pre-built Composio enterprise toolkits
                             (Gmail, Slack, Jira, …) and registers them.
"""

import logging
import os
from typing import Any, List, Optional

from backend.tools.registry import TOOL_REGISTRY, register_langchain_tool

logger = logging.getLogger("voicerag.tools.integrations")

# ---------------------------------------------------------------------------
# Optional LangChain integration
# ---------------------------------------------------------------------------
try:
    from langchain_core.tools import StructuredTool, BaseTool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    BaseTool = Any  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Optional Composio integration
# ---------------------------------------------------------------------------
try:
    from composio import Composio
    from composio_langchain import LangchainProvider
    COMPOSIO_AVAILABLE = True
except ImportError:
    COMPOSIO_AVAILABLE = False


def get_langchain_tools() -> List[Any]:
    """
    Converts all registered tools into native LangChain ``StructuredTool``
    instances.

    Allows the entire Voice-RAG toolset to be used inside any LangChain
    Agent, LCEL Chain, or LangGraph graph.

    Returns:
        List of ``StructuredTool`` objects.

    Raises:
        ImportError: If ``langchain-core`` is not installed.
    """
    if not LANGCHAIN_AVAILABLE:
        raise ImportError(
            "langchain-core is required to export LangChain tools. "
            "Run: pip install langchain-core"
        )

    lc_tools = []
    for name, entry in TOOL_REGISTRY.items():
        try:
            lc_t = StructuredTool.from_function(
                func=entry["func"],
                name=name,
                description=entry["description"],
            )
            lc_tools.append(lc_t)
        except Exception as e:
            logger.debug(f"Could not convert tool '{name}' to LangChain: {e}")
    return lc_tools


def load_composio_tools(
    api_key: Optional[str] = None,
    toolkits: Optional[List[str]] = None,
    tools: Optional[List[str]] = None,
    user_id: str = "default",
) -> List[str]:
    """
    Loads pre-built enterprise tools from Composio (e.g. Gmail, Google Sheets,
    Slack, Jira, GitHub) and registers them into the central TOOL_REGISTRY.

    Example::

        loaded = load_composio_tools(toolkits=["gmail", "slack"])

    Args:
        api_key:   Composio API key (falls back to ``COMPOSIO_API_KEY`` env var).
        toolkits:  List of Composio toolkit names to load (e.g. ``["gmail"]``).
        tools:     List of specific Composio action names to load.
        user_id:   Composio user/entity identifier.

    Returns:
        List of registered tool names that were successfully loaded.

    Raises:
        ImportError: If ``composio-core`` / ``composio-langchain`` are not installed.
    """
    if not COMPOSIO_AVAILABLE:
        raise ImportError(
            "composio-core and composio-langchain are required. "
            "Run: pip install composio-core composio-langchain"
        )

    key = api_key or os.getenv("COMPOSIO_API_KEY")
    if not key:
        logger.warning(
            "No COMPOSIO_API_KEY provided or found in environment. "
            "Set COMPOSIO_API_KEY to load Composio tools."
        )
        return []

    try:
        provider = LangchainProvider()
        c = Composio(api_key=key, provider=provider)
        fetch_kwargs: dict = {"user_id": user_id}
        if toolkits:
            fetch_kwargs["toolkits"] = toolkits
        if tools:
            fetch_kwargs["tools"] = tools

        lc_tools = c.tools.get(**fetch_kwargs)
        registered_names: List[str] = []
        for t in lc_tools:
            register_langchain_tool(t)
            registered_names.append(t.name)

        logger.info(
            "Loaded and registered %d Composio tools into registry: %s",
            len(registered_names),
            registered_names,
        )
        return registered_names
    except Exception as e:
        logger.error(f"Error loading Composio tools: {e}")
        return []
