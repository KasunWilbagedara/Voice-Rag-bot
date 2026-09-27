"""
backend/tools/__init__.py — Tools Package Public API
=====================================================
Re-exports every symbol that was previously importable from
``backend.tools`` (the old flat ``tools.py`` module) so that all existing
code continues to work without modification.

Original flat module:  ``backend/tools.py``
Refactored package:    ``backend/tools/``

Sub-modules (import order matters — registry must load first)
--------------------------------------------------------------
registry        — TOOL_REGISTRY, register_tool, call_tool, list_tools
external_tools  — get_live_weather, web_search, get_current_datetime,
                  calculate_expression  (registered on import)
db_tools        — track_customer_order, track_support_ticket,
                  lookup_student, execute_sql, list_databases,
                  get_database_schema, get_session_memories,
                  save_session_memory, search_knowledge_base
                  (registered on import)
integrations    — get_langchain_tools, load_composio_tools
"""

# 1. Registry MUST be imported first (defines TOOL_REGISTRY dict)
from backend.tools.registry import (
    TOOL_REGISTRY,
    register_tool,
    register_external_tool,
    register_langchain_tool,
    call_tool,
    list_tools,
)

# 2. Tool modules — importing them executes their @register_tool decorators,
#    populating TOOL_REGISTRY as a side-effect.
import backend.tools.external_tools  # noqa: F401
import backend.tools.db_tools        # noqa: F401

# 3. LangChain / Composio integration helpers
from backend.tools.integrations import get_langchain_tools, load_composio_tools

__all__ = [
    # Registry
    "TOOL_REGISTRY",
    "register_tool",
    "register_external_tool",
    "register_langchain_tool",
    "call_tool",
    "list_tools",
    # Integrations
    "get_langchain_tools",
    "load_composio_tools",
]
