"""
backend/auth.py — User accounts (username + password) and login tokens
=======================================================================
Stored in the same SQLite file as the rest of the app. Passwords are hashed
with PBKDF2-SHA256 (Python standard library). A login returns a random token
that the client sends back as ``Authorization: Bearer <token>``.
"""

import hashlib
import hmac
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import Header, HTTPException

import backend.db as db
from backend.config import AUTH_REQUIRED

TOKEN_LIFETIME = timedelta(days=30)
_PBKDF2_ROUNDS = 200_000
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db.SQLITE_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        " id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,"
        " password_hash TEXT NOT NULL, created_at TEXT NOT NULL);"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS auth_tokens ("
        " token TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL);"
    )
    return conn


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return f"{salt}${digest.hex()}"


def _check_password(password: str, stored: str) -> bool:
    salt = stored.split("$", 1)[0]
    return hmac.compare_digest(_hash_password(password, salt), stored)


def _new_token(conn: sqlite3.Connection, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO auth_tokens (token, user_id, created_at) VALUES (?, ?, ?);",
        (token, user_id, datetime.utcnow().isoformat()),
    )
    conn.commit()
    return token


def register(username: str, password: str) -> Dict[str, str]:
    """Creates an account and logs it in. Returns {"token", "user"}."""
    username = (username or "").strip()
    if not _USERNAME_RE.match(username):
        raise ValueError("Username must be 3-32 characters: letters, numbers, '.', '_' or '-'.")
    if len(password or "") < 8:
        raise ValueError("Password must be at least 8 characters.")

    conn = _connect()
    try:
        if conn.execute("SELECT 1 FROM users WHERE username = ?;", (username,)).fetchone():
            raise ValueError("That username is already taken.")
        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?);",
            (user_id, username, _hash_password(password), datetime.utcnow().isoformat()),
        )
        return {"token": _new_token(conn, user_id), "user": {"id": user_id, "username": username}}
    finally:
        conn.close()


def login(username: str, password: str) -> Dict[str, str]:
    """Checks the password and returns {"token", "user"}."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?;", ((username or "").strip(),)
        ).fetchone()
        if not row or not _check_password(password or "", row[2]):
            raise ValueError("Wrong username or password.")
        return {"token": _new_token(conn, row[0]), "user": {"id": row[0], "username": row[1]}}
    finally:
        conn.close()


def logout(token: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM auth_tokens WHERE token = ?;", (token,))
    conn.commit()
    conn.close()


def user_for_token(token: Optional[str]) -> Optional[Dict[str, str]]:
    """The user a (non-expired) token belongs to, or None."""
    if not token:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT u.id, u.username, t.created_at FROM auth_tokens t JOIN users u ON u.id = t.user_id "
            "WHERE t.token = ?;",
            (token,),
        ).fetchone()
        if not row:
            return None
        if datetime.utcnow() - datetime.fromisoformat(row[2]) > TOKEN_LIFETIME:
            conn.execute("DELETE FROM auth_tokens WHERE token = ?;", (token,))
            conn.commit()
            return None
        return {"id": row[0], "username": row[1]}
    finally:
        conn.close()


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user_id(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
    """
    FastAPI dependency: the logged-in user's id, used as their session id so
    memory and chat history are private to each person.

    Returns None (callers fall back to the request's sessionId) only when
    AUTH_REQUIRED is turned off; otherwise a missing/invalid token is a 401.
    """
    user = user_for_token(bearer_token(authorization))
    if user:
        return user["id"]
    if AUTH_REQUIRED:
        raise HTTPException(status_code=401, detail="Please log in.")
    return None
