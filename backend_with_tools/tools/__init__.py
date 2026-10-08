"""
Modular Tools Package for Voice-RAG Bot.

Every tool has its own dedicated file:
- weather.py              -> get_live_weather
- web_search.py           -> web_search
- datetime_tool.py        -> get_current_datetime
- calculator.py           -> calculate_expression
- order_tracking.py       -> track_customer_order
- ticket_tracking.py      -> track_support_ticket
- student_lookup.py       -> lookup_student
- sql_executor.py         -> execute_sql
- database_inspection.py  -> list_databases, get_database_schema
- session_memory.py       -> get_session_memories, save_session_memory
- knowledge_search.py     -> search_knowledge_base
- base.py                 -> Central registry, call_tool, LangChain & Composio adapters
"""

from backend_with_tools.tools.base import (
    TOOL_REGISTRY,
    register_tool,
    register_external_tool,
    register_langchain_tool,
    call_tool,
    list_tools,
    get_langchain_tools,
    load_composio_tools,
)

# Import each individual tool module so decorators register them automatically
from backend_with_tools.tools.weather import get_live_weather
from backend_with_tools.tools.web_search import web_search
from backend_with_tools.tools.datetime_tool import get_current_datetime
from backend_with_tools.tools.calculator import calculate_expression
from backend_with_tools.tools.order_tracking import track_customer_order
from backend_with_tools.tools.ticket_tracking import track_support_ticket
from backend_with_tools.tools.student_lookup import lookup_student
from backend_with_tools.tools.sql_executor import execute_sql
from backend_with_tools.tools.database_inspection import list_databases, get_database_schema
from backend_with_tools.tools.session_memory import get_session_memories, save_session_memory
from backend_with_tools.tools.knowledge_search import search_knowledge_base
from backend_with_tools.tools.mcp_bridge import MCPBridge

__all__ = [
    # Registry & helpers
    "TOOL_REGISTRY",
    "register_tool",
    "register_external_tool",
    "register_langchain_tool",
    "call_tool",
    "list_tools",
    "get_langchain_tools",
    "load_composio_tools",
    "MCPBridge",
    # Individual tools
    "get_live_weather",
    "web_search",
    "get_current_datetime",
    "calculate_expression",
    "track_customer_order",
    "track_support_ticket",
    "lookup_student",
    "execute_sql",
    "list_databases",
    "get_database_schema",
    "get_session_memories",
    "save_session_memory",
    "search_knowledge_base",
]
