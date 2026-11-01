"""
backend/security.py — Shared CORS settings and admin-key guard
===============================================================
"""

import hmac
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException

from backend.config import ADMIN_API_KEY, CORS_ORIGINS


def cors_kwargs() -> Dict[str, Any]:
    """Keyword arguments for ``CORSMiddleware`` (explicit origins, no wildcard)."""
    return {
        "allow_origins": CORS_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


def admin_headers() -> Dict[str, str]:
    """Headers to attach to service-to-service calls of protected endpoints."""
    return {"x-admin-key": ADMIN_API_KEY} if ADMIN_API_KEY else {}


def require_admin(x_admin_key: Optional[str] = Header(default=None, alias="x-admin-key")) -> None:
    """
    FastAPI dependency protecting destructive endpoints.

    No-op when ``ADMIN_API_KEY`` is unset (local development); otherwise the
    request must carry a matching ``x-admin-key`` header.
    """
    if not ADMIN_API_KEY:
        return
    if not x_admin_key or not hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Missing or invalid admin key.")
