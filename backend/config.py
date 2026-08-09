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
PORT = int(os.getenv("PORT", "8000"))

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
