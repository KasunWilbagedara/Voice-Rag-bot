"""
rag_v2/storage/memory.py
------------------------
Conversation memory operations backed by the rag_v2_chat_history table.
"""

import logging
from typing import Dict, List

import psycopg2

from rag_v2.storage.db import get_db_connection

logger = logging.getLogger("rag_v2.storage.memory")


def save_message(session_id: str, role: str, content: str) -> None:
    """Persist a single conversational turn to the database.

    Args:
        session_id: Unique identifier for the chat session.
        role:       Speaker role — typically ``"user"`` or ``"assistant"``.
        content:    The text of the message.

    Raises:
        Nothing — errors are logged and swallowed so a DB hiccup never
        crashes the caller's hot path.
    """
    sql = """
        INSERT INTO rag_v2_chat_history (session_id, role, content)
        VALUES (%s, %s, %s);
    """
    try:
        with get_db_connection() as conn:
            if conn is None:
                logger.warning(
                    "save_message: DB unavailable — message NOT persisted "
                    "(session=%s, role=%s).",
                    session_id,
                    role,
                )
                return
            with conn.cursor() as cur:
                cur.execute(sql, (session_id, role, content))
            conn.commit()
            logger.debug(
                "save_message: persisted turn (session=%s, role=%s, len=%d).",
                session_id,
                role,
                len(content),
            )
    except psycopg2.Error as exc:
        logger.error("save_message failed (session=%s): %s", session_id, exc)
    except Exception as exc:
        logger.error(
            "save_message unexpected error (session=%s): %s", session_id, exc
        )


def get_history(session_id: str, limit: int = 20) -> List[Dict[str, str]]:
    """Retrieve the most recent *limit* turns for a session.

    Returns:
        A list of ``{"role": ..., "content": ...}`` dicts ordered from oldest
        to newest.  Returns an empty list if the DB is unavailable or the
        session has no history.
    """
    sql = """
        SELECT role, content
        FROM rag_v2_chat_history
        WHERE session_id = %s
        ORDER BY created_at ASC
        LIMIT %s;
    """
    try:
        with get_db_connection() as conn:
            if conn is None:
                logger.warning(
                    "get_history: DB unavailable — returning empty history "
                    "(session=%s).",
                    session_id,
                )
                return []
            with conn.cursor() as cur:
                cur.execute(sql, (session_id, limit))
                rows = cur.fetchall()
            history = [{"role": row[0], "content": row[1]} for row in rows]
            logger.debug(
                "get_history: fetched %d turns (session=%s, limit=%d).",
                len(history),
                session_id,
                limit,
            )
            return history
    except psycopg2.Error as exc:
        logger.error("get_history failed (session=%s): %s", session_id, exc)
        return []
    except Exception as exc:
        logger.error(
            "get_history unexpected error (session=%s): %s", session_id, exc
        )
        return []


def clear_history(session_id: str) -> int:
    """Delete all history rows for *session_id*.

    Returns:
        The number of rows deleted, or ``0`` if the DB is unavailable or
        nothing was deleted.
    """
    sql = """
        DELETE FROM rag_v2_chat_history
        WHERE session_id = %s;
    """
    try:
        with get_db_connection() as conn:
            if conn is None:
                logger.warning(
                    "clear_history: DB unavailable — nothing deleted "
                    "(session=%s).",
                    session_id,
                )
                return 0
            with conn.cursor() as cur:
                cur.execute(sql, (session_id,))
                deleted = cur.rowcount
            conn.commit()
            logger.info(
                "clear_history: deleted %d rows (session=%s).",
                deleted,
                session_id,
            )
            return deleted
    except psycopg2.Error as exc:
        logger.error("clear_history failed (session=%s): %s", session_id, exc)
        return 0
    except Exception as exc:
        logger.error(
            "clear_history unexpected error (session=%s): %s", session_id, exc
        )
        return 0
