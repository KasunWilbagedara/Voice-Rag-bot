"""
Persistent Session Memory Tools.

Allows saving and retrieving persistent user identities, preferences, and session facts.
"""

import logging
from typing import List, Dict, Any

from backend_with_tools.db import get_user_memories, save_or_update_memory
from backend_with_tools.tools.base import register_tool

logger = logging.getLogger("voicerag.tools.session_memory")


@register_tool(
    name="get_session_memories",
    description="Retrieves all persistent remembered facts, identities, and entities stored for a user session.",
)
def get_session_memories(session_id: str = "default_user") -> List[Dict[str, Any]]:
    """Fetches user memories for the given session ID."""
    return get_user_memories(session_id)


@register_tool(
    name="save_session_memory",
    description="Saves or updates a persistent user fact, entity, or preference (e.g., user_name, last_tracked_order).",
)
def save_session_memory(session_id: str, key: str, value: str, category: str = "general") -> bool:
    """Stores a fact into persistent memory."""
    try:
        save_or_update_memory(session_id=session_id, key=key, value=value, category=category)
        return True
    except Exception as e:
        logger.warning(f"Failed to save session memory: {e}")
        return False
