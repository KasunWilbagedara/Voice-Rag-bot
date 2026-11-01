import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env.local"))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("POSTGRES_URL", "postgresql://postgres:postgrespassword@localhost:5432/voicerag")
)

# RAG & Voice Service port (Port 8000)
PORT = int(os.getenv("PORT", "8000"))

# Tool Execution Service port (Port 8001)
TOOL_PORT = int(os.getenv("TOOL_PORT", "8001"))

# URL for the Tool Execution Service.
# Override via TOOL_SERVICE_URL env var for container environments
# e.g. TOOL_SERVICE_URL=http://tool-service:8001/api/tools/call
TOOL_SERVICE_URL = os.getenv(
    "TOOL_SERVICE_URL",
    f"http://127.0.0.1:{TOOL_PORT}/api/tools/call",
)
# On Windows "localhost" tries IPv6 (::1) first and waits ~2 s before falling
# back to IPv4, which made every tool call ~2 s slower. Use IPv4 directly.
TOOL_SERVICE_URL = TOOL_SERVICE_URL.replace("://localhost:", "://127.0.0.1:")

# Browser origins allowed to call the Python services directly (comma-separated).
# The Next.js UI calls the backends server-side through its /api proxy routes,
# so in the default setup only the UI origin needs to be listed.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

# Shared secret for destructive / administrative endpoints (document upload &
# delete, database connect/reset/seed, student writes, raw tool calls).
# When set, callers must send it in the ``x-admin-key`` header; the Next.js
# proxy forwards it automatically. Leave empty for local development.
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

# User accounts: when true (default) chat, voice, memory and history endpoints
# need a logged-in user, and each user gets their own memory and history.
# Set AUTH_REQUIRED=false for local scripts/tests that call the API directly.
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").strip().lower() not in ("0", "false", "no")


def get_api_key(custom_api_key: str = None) -> str:
    key = custom_api_key or GEMINI_API_KEY or OPENAI_API_KEY
    if not key:
        raise ValueError("API Key is required. Please provide a Google Gemini API Key or OpenAI API Key.")
    return key


def is_gemini_key(key: str = None) -> bool:
    api_key = key or GEMINI_API_KEY or OPENAI_API_KEY or ""
    if not api_key:
        return False
    return api_key.startswith("AIza") or api_key.startswith("AQ.") or not api_key.startswith("sk-")
